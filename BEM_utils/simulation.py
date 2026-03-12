"""
simulation.py — EnergyPlus Simulation Runner (Phase 3).

Provides:
- run_simulation()            Single IDF simulation with ExpandObjects support
- run_simulations_parallel()  ProcessPoolExecutor-based parallel batch runner
"""
import os
import subprocess
import platform
import shutil
import time
import threading
from concurrent.futures import ProcessPoolExecutor, as_completed


def run_simulation(idf_path, epw_path, output_dir, ep_path, n_jobs=1, quiet=False):
    """
    Runs a single EnergyPlus simulation.

    Pipeline:
      1. Create output_dir
      2. Copy IDF  →  output_dir/in.idf
      3. Copy Energy+.idd  →  output_dir/  (required by ExpandObjects)
      4. Run ExpandObjects (expands HVACTemplate:* objects; no-op if none present)
      5. Determine simulation IDF (expanded.idf if it exists, else in.idf)
      6. Run EnergyPlus

    Args:
        idf_path:   Path to the (already optimized) IDF file.
        epw_path:   Path to the EPW weather file.
        output_dir: Directory to store all simulation outputs.
        ep_path:    Path to EnergyPlus executable OR its directory.
        n_jobs:     Internal EnergyPlus thread count (-j flag).
        quiet:      Suppress verbose stdout/stderr (useful for parallel runs).

    Returns:
        dict: {'success': bool, 'name': str, 'message': str, 'output_dir': str}
    """
    name = os.path.basename(idf_path)

    try:
        os.makedirs(output_dir, exist_ok=True)

        exe_ext = '.exe' if platform.system() == 'Windows' else ''

        # Resolve executable and its parent directory
        if os.path.isdir(ep_path):
            ep_dir = ep_path
            ep_exe = os.path.join(ep_path, f'energyplus{exe_ext}')
        else:
            ep_dir = os.path.dirname(ep_path)
            ep_exe = ep_path

        if not os.path.exists(ep_exe):
            msg = f"EnergyPlus executable not found: {ep_exe}"
            if not quiet:
                print(f"  [ERROR] {msg}")
            return {'success': False, 'name': name, 'message': msg, 'output_dir': output_dir}

        # Copy IDF into output_dir
        in_idf_path = os.path.join(output_dir, 'in.idf')
        shutil.copy2(idf_path, in_idf_path)

        # Copy Energy+.idd — required for ExpandObjects to find the schema
        idd_path = os.path.join(ep_dir, 'Energy+.idd')
        if os.path.exists(idd_path):
            shutil.copy2(idd_path, os.path.join(output_dir, 'Energy+.idd'))
        elif not quiet:
            print(f"  [WARNING] Energy+.idd not found at {idd_path} — ExpandObjects may fail if needed.")

        # Build EnergyPlus command
        # We use -x to let EnergyPlus handle ExpandObjects internally if needed.
        # This is more robust than calling the ExpandObjects binary directly.
        cmd = [ep_exe, '-w', epw_path, '-d', output_dir, '-x']
        if n_jobs > 1:
            cmd += ['-j', str(n_jobs)]
        cmd.append(in_idf_path)

        if not quiet:
            print(f"  Running EnergyPlus for: {name}")

        subprocess.run(cmd, check=True, capture_output=quiet)

        msg = f"Simulation completed: {name}"
        if not quiet:
            print(f"  [OK] {msg}")
        return {'success': True, 'name': name, 'message': msg, 'output_dir': output_dir}

    except subprocess.CalledProcessError as e:
        msg = f"Simulation failed: {name} — {e}"
        if not quiet:
            print(f"  [FAIL] {msg}")
        return {'success': False, 'name': name, 'message': msg, 'output_dir': output_dir}
    except Exception as e:
        msg = f"Unexpected error for {name}: {e}"
        if not quiet:
            print(f"  [ERROR] {msg}")
        return {'success': False, 'name': name, 'message': msg, 'output_dir': output_dir}


def _run_simulation_wrapper(args):
    """Pickle-safe wrapper for ProcessPoolExecutor (must be module-level)."""
    return run_simulation(
        idf_path=args['idf'],
        epw_path=args['epw'],
        output_dir=args['output_dir'],
        ep_path=args['ep_path'],
        n_jobs=args.get('n_jobs', 1),
        quiet=args.get('quiet', True),
    )


def run_simulations_parallel(simulation_jobs, ep_path, max_workers=None):
    """
    Runs multiple EnergyPlus simulations in parallel using ProcessPoolExecutor.

    Each worker runs with n_jobs=1 to avoid CPU over-subscription:
    N parallel sims × 1 thread each = N total threads (correct).
    N parallel sims × M threads each = N×M total threads (too many).

    Args:
        simulation_jobs: List of dicts with keys: 'idf', 'epw', 'output_dir', 'name'.
        ep_path:         Path to EnergyPlus executable or directory.
        max_workers:     Max concurrent simulations (default: CPU count).

    Returns:
        dict: {'successful': list, 'failed': list, 'total_time': float}
    """
    if max_workers is None:
        max_workers = os.cpu_count() or 4
    max_workers = min(max_workers, len(simulation_jobs))

    # Attach runtime args to each job copy
    jobs = []
    for job in simulation_jobs:
        j = job.copy()
        # Use existing ep_path if provided (for version-specific runs), else use default
        if 'ep_path' not in j:
            j['ep_path'] = ep_path
        j['n_jobs'] = 1
        j['quiet'] = True
        jobs.append(j)

    print(f"\n{'='*60}")
    print(f"Starting {len(jobs)} simulations with {max_workers} parallel workers")
    print(f"{'='*60}")

    successful = []
    failed = []
    start_time = time.time()
    completed = 0

    # Background thread: prints elapsed time every 30 s
    stop_event = threading.Event()

    def progress_monitor():
        last = 0
        while not stop_event.is_set():
            elapsed = time.time() - start_time
            mins, secs = divmod(int(elapsed), 60)
            if completed == last:
                print(f"  [SIM] Running... [{completed}/{len(jobs)}] Elapsed: {mins:02d}:{secs:02d}", flush=True)
            last = completed
            stop_event.wait(30)

    monitor = threading.Thread(target=progress_monitor, daemon=True)
    monitor.start()

    try:
        with ProcessPoolExecutor(max_workers=max_workers) as executor:
            futures = {executor.submit(_run_simulation_wrapper, job): job for job in jobs}
            for future in as_completed(futures):
                completed += 1
                job = futures[future]
                job_name = job.get('name', os.path.basename(job['idf']))
                elapsed = time.time() - start_time
                mins, secs = divmod(int(elapsed), 60)
                try:
                    result = future.result()
                    if result['success']:
                        successful.append(result)
                        print(f"  [{completed}/{len(jobs)}] [OK]   {job_name} ({mins:02d}:{secs:02d})")
                    else:
                        failed.append(result)
                        print(f"  [{completed}/{len(jobs)}] [FAIL] {job_name} ({mins:02d}:{secs:02d})")
                except Exception as e:
                    failed.append({'name': job_name, 'message': str(e), 'success': False})
                    print(f"  [{completed}/{len(jobs)}] [ERR]  {job_name} — {e}")
    finally:
        stop_event.set()
        monitor.join(timeout=1)

    elapsed = time.time() - start_time
    print(f"\n{'='*60}")
    print(f"SUMMARY  |  Total: {elapsed:.1f}s  |  OK: {len(successful)}  |  Failed: {len(failed)}")
    print(f"{'='*60}")

    return {'successful': successful, 'failed': failed, 'total_time': elapsed}
