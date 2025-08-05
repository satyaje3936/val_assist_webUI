#!/usr/bin/env python3
"""
Python script to remove all HSD batch and consolidated files
This script removes files matching these patterns:
- hsd_batch*.json (HSD batch JSON files)
- batch_processing_summary* (Batch processing summary files)
- consolidated_ai* (Consolidated AI files)  
- consolidated_hsd* (Consolidated HSD files)
"""

import os
import glob
import argparse
import sys
from pathlib import Path

def main():
    parser = argparse.ArgumentParser(description="Remove HSD batch and consolidated files")
    parser.add_argument("--whatif", action="store_true", 
                       help="Show what files would be deleted without actually deleting them")
    parser.add_argument("--force", action="store_true", 
                       help="Skip confirmation prompts")
    parser.add_argument("--path", default=".", 
                       help="Directory path to search for files (default: current directory)")
    
    args = parser.parse_args()
    
    # Define the patterns for files to delete
    patterns = [
        "hsd_batch*.json",           # HSD batch JSON files
        "batch_processing_summary*", # Batch processing summary files
        "consolidated_ai*",          # Consolidated AI files
        "consolidated_hsd*",         # Consolidated HSD files
        "hsd_query*"
    ]
    search_path = Path(args.path).resolve()
    
    print(f"🔍 Searching for batch-related files in: {search_path}")
    print(f"   Patterns: {', '.join(patterns)}")
    
    # Find all matching files
    files_to_delete = []
    for pattern in patterns:
        files_to_delete.extend(search_path.glob(pattern))
    
    if not files_to_delete:
        print("✅ No batch-related files found to delete.")
        return 0
    
    # Remove duplicates and sort by name
    files_to_delete = sorted(set(files_to_delete), key=lambda x: x.name)
    
    print(f"📋 Found {len(files_to_delete)} batch-related file(s):")
    for file_path in files_to_delete:
        size_kb = round(file_path.stat().st_size / 1024, 2)
        file_type = "JSON" if file_path.suffix.lower() == ".json" else file_path.suffix.upper().lstrip('.')
        print(f"   • {file_path.name} ({size_kb} KB) [{file_type}]")
    
    if args.whatif:
        print("\n🔍 WhatIf mode: These files would be deleted:")
        for file_path in files_to_delete:
            print(f"   - Would delete: {file_path.name}")
        print("\nTo actually delete these files, run the script without --whatif parameter.")
        return 0
    
    # Confirmation prompt (unless --force is used)
    if not args.force:
        confirmation = input(f"\n⚠️  Are you sure you want to delete these {len(files_to_delete)} files? [Y/N]: ")
        
        if confirmation.lower() not in ['y', 'yes']:
            print("❌ Deletion cancelled by user.")
            return 0
    
    # Delete the files
    print("\n🗑️  Deleting batch-related files...")
    
    deleted_count = 0
    error_count = 0
    
    for file_path in files_to_delete:
        try:
            file_path.unlink()
            print(f"   ✅ Deleted: {file_path.name}")
            deleted_count += 1
        except Exception as e:
            print(f"   ❌ Failed to delete: {file_path.name} - {e}")
            error_count += 1
    
    # Summary
    print("\n📊 Cleanup Summary:")
    print(f"   • Files found: {len(files_to_delete)}")
    print(f"   • Successfully deleted: {deleted_count}")
    if error_count > 0:
        print(f"   • Errors: {error_count}")
    
    if deleted_count == len(files_to_delete):
        print("\n✅ All batch-related files have been successfully removed!")
        return 0
    elif deleted_count > 0:
        print(f"\n⚠️  Some files were deleted, but {error_count} errors occurred.")
        return 1
    else:
        print("\n❌ No files were deleted due to errors.")
        return 1

if __name__ == "__main__":
    sys.exit(main())
