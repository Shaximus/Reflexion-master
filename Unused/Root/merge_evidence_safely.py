import json
from pathlib import Path
import os
from datetime import datetime

# Define the exact path
evidence_path = Path(r"F:\Reflexion_ultimate\vigilante\hunt_data\evidence")

if not evidence_path.exists():
    print(f"ERROR: Path {evidence_path} doesn't exist!")
    exit(1)

# Find all JSON files
json_files = list(evidence_path.glob("*.json"))
print(f"\nFound {len(json_files)} JSON files in {evidence_path}")

if len(json_files) == 0:
    print("No JSON files found!")
    exit(1)

# Show what we're about to do
print(f"\nWill merge {len(json_files)} files into MERGED_EVIDENCE.json")
print("Original files will NOT be deleted automatically")
response = input("\nContinue with merge? (yes/no): ")

if response.lower() != 'yes':
    print("Aborted - no changes made")
    exit(0)

# Create merged data structure
merged_data = {
    "metadata": {
        "merge_date": datetime.now().isoformat(),
        "total_files": len(json_files),
        "source_path": str(evidence_path)
    },
    "evidence": {}
}

# Read each file SAFELY
failed_files = []
successful = 0

for i, json_file in enumerate(json_files):
    try:
        with open(json_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
            
        # Use filename (without .json) as key
        key = json_file.stem
        
        # Handle duplicate keys
        if key in merged_data["evidence"]:
            key = f"{key}_{i}"
            
        merged_data["evidence"][key] = data
        successful += 1
        
        if (i + 1) % 100 == 0:
            print(f"Progress: {i+1}/{len(json_files)} files processed")
            
    except Exception as e:
        print(f"WARNING: Failed to read {json_file.name}: {e}")
        failed_files.append(str(json_file))

# Save merged file in the PARENT directory (not in evidence folder)
output_path = evidence_path.parent / "MERGED_EVIDENCE.json"

print(f"\nWriting merged data to {output_path}")
with open(output_path, 'w', encoding='utf-8') as f:
    json.dump(merged_data, f, indent=2)

# Report results
file_size = output_path.stat().st_size / (1024 * 1024)
print(f"\n? SUCCESS!")
print(f"  Merged {successful} files successfully")
print(f"  Output file: {output_path}")
print(f"  Size: {file_size:.2f} MB")

if failed_files:
    print(f"\n?? Failed to read {len(failed_files)} files:")
    for f in failed_files[:5]:
        print(f"    {f}")
    if len(failed_files) > 5:
        print(f"    ... and {len(failed_files)-5} more")

print(f"\n?? Original files are still in: {evidence_path}")
print("They have NOT been deleted")

# Only offer to delete if merge was 100% successful
if successful == len(json_files) and not failed_files:
    print("\n" + "="*50)
    print("DELETE ORIGINALS?")
    print("="*50)
    print(f"The merge was successful for all {successful} files")
    print("Would you like to delete the original JSON files?")
    print("?? This cannot be undone!")
    
    delete_response = input("\nDelete original files? (type 'DELETE' to confirm): ")
    
    if delete_response == 'DELETE':
        print("\nDeleting original files...")
        for json_file in json_files:
            json_file.unlink()
        print(f"? Deleted {len(json_files)} original files")
    else:
        print("? Deletion cancelled - original files preserved")
else:
    print("\n?? Not offering deletion due to failed files")

print("\nDone!")
