import os
import subprocess
import glob

def run_conversion():
    # Define mapping of source folders to converter scripts
    # Key: folder name in 'source/', Value: python script to run
    converters = {
        "Series_16": "convert_pdf.py",
        "Globe": "convert_globe.py",
        "Jeffco": "convert_jeffco.py"
    }

    base_source_dir = "source"
    
    print("=== Starting Batch Conversion ===\n")

    for folder, script in converters.items():
        source_path = os.path.join(base_source_dir, folder)
        if not os.path.exists(source_path):
            print(f"Skipping {folder}: Directory not found.")
            continue
            
        print(f"--- Processing {folder} using {script} ---")
        
        # Check if python script exists
        if not os.path.exists(script):
             print(f"Error: Converter script {script} not found.")
             continue

        # Run the script
        # Since the scripts currently look for hardcoded paths or globs, 
        # we assume they are configured to read from source/{folder} and write to output/{folder}
        try:
            result = subprocess.run(["python3", script], capture_output=True, text=True)
            if result.returncode == 0:
                print(f"Success: {script} finished.")
                # print(result.stdout) # Optional: print script output
            else:
                print(f"Error executing {script}:")
                print(result.stderr)
        except Exception as e:
            print(f"Failed to run {script}: {e}")
        
        print("")

    print("=== Running Validation ===\n")
    try:
        subprocess.run(["python3", "validate_output.py"], check=True)
    except subprocess.CalledProcessError:
        print("Validation process reported errors.")

if __name__ == "__main__":
    run_conversion()
