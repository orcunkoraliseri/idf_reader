# Parallel Simulation Runner

Add parallel processing capability to run multiple EnergyPlus simulations concurrently, significantly reducing total simulation time.

## Proposed Changes

### bem_utils/runner.py

#### New Function: `run_simulations_parallel`
```python
def run_simulations_parallel(simulation_jobs, ep_path, max_workers=None):
    """
    Run multiple simulations in parallel.
    
    Args:
        simulation_jobs: List of dicts with keys: 'idf', 'epw', 'output_dir', 'name'
        ep_path: Path to EnergyPlus executable
        max_workers: Max concurrent simulations (default: CPU count)
    
    Returns:
        Dict with results: {'successful': [...], 'failed': [...]}
    """
```

**Key implementation details:**
- Use `concurrent.futures.ProcessPoolExecutor` for true parallelism
- Each simulation runs in its own process (EnergyPlus is CPU-bound)
- Progress bar and status updates for user feedback
- Collect and report results (success/failure) for each simulation

#### Refactor: `run_simulation`
- Add return value (success/failure status) for parallel runner integration
- Suppress verbose output when running in parallel mode (optional `quiet` parameter)

---

### main_file.py

#### Option 3: "Run all simulations" - Modified
```diff
elif choice == '3':
    confirm = input(f"This will run {len(pairs)} simulations. Continue? (y/n): ")
    if confirm.lower() == 'y':
+       max_cpus = os.cpu_count()
+       n_workers = input(f"Max parallel simulations (default {max_cpus}): ").strip()
+       n_workers = int(n_workers) if n_workers else max_cpus
+       
+       jobs = [{'idf': p['idf'], 'epw': p['epw'], 
+                'output_dir': os.path.join(base_dir, 'SimResults', p['name'].replace('.idf','')),
+                'name': p['name']} for p in pairs]
+       runner.run_simulations_parallel(jobs, ENERGYPLUS_EXE, max_workers=n_workers)
```

#### New Option 6: "Run custom batch from directory"
Allow user to specify a directory containing IDF files and run them all in parallel.

---

## Architecture Diagram

```
                    main_file.py
                         │
                         ▼
              ┌──────────────────────┐
              │ Build simulation job │
              │ list from pairs      │
              └──────────────────────┘
                         │
                         ▼
              ┌──────────────────────┐
              │ run_simulations_     │
              │ parallel()           │
              └──────────────────────┘
                         │
         ┌───────────────┼───────────────┐
         ▼               ▼               ▼
   ┌──────────┐   ┌──────────┐   ┌──────────┐
   │ Worker 1 │   │ Worker 2 │   │ Worker N │
   │ run_sim  │   │ run_sim  │   │ run_sim  │
   └──────────┘   └──────────┘   └──────────┘
         │               │               │
         ▼               ▼               ▼
   ┌──────────┐   ┌──────────┐   ┌──────────┐
   │ E+ sim1  │   │ E+ sim2  │   │ E+ simN  │
   └──────────┘   └──────────┘   └──────────┘
```

---

## Notes

**EnergyPlus internal `-j` flag vs. process-level parallelism:**  
The current single-simulation `-j` flag uses multiple threads *within* one simulation. The new parallel runner runs *multiple simulations* concurrently. These can be combined, but may oversubscribe CPU. Recommend setting internal threads to 1 when running many simulations in parallel.

---

## Status: APPROVED

Ready for implementation.
