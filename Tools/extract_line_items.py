#!/usr/bin/env python3
"""
Extract lineItem attributes from C# fuse rule files
"""
import re
import pandas as pd
from pathlib import Path
from datetime import datetime

def extract_line_items_from_text(text):
    """
    Extract lineItem attributes from text
    
    Args:
        text (str): Input text/code
        
    Returns:
        list: List of unique lineItem attributes
    """
    # Pattern to match lineItem.AttributeName (can start with letter, underscore, or number, contain letters, numbers, underscores)
    pattern = r'lineItem\.([a-zA-Z0-9_][a-zA-Z0-9_]*)'
    
    matches = re.findall(pattern, text)
    return sorted(list(set(matches)))  # Remove duplicates and sort

def extract_line_items_from_file(file_path):
    """
    Extract lineItem attributes from specific fuse equation types in C# file
    
    Targets:
    - Lines starting with "Fuses.Direct" (with FuseSetValue or FuseBinaryValue)
    - Lines starting with "Fuses.Virtual" (with FuseSetValue or FuseBinaryValue)
    - Lines starting with "LIRAMappingWrapper"
    
    Args:
        file_path (str): Path to the C# file
        
    Returns:
        dict: Dictionary with line numbers and extracted items
    """
    lineitem_pattern = r'lineItem\.([a-zA-Z0-9_][a-zA-Z0-9_]*)'
    fuse_name_pattern = r'Fuses\.(Direct|Virtual)\.(.+?)\.(FuseSetValue|FuseBinaryValue)'
    value_pattern = r'FuseSetValue\s*=\s*(.+?);'
    binary_value_pattern = r'FuseBinaryValue\s*=\s*(.+?);'
    lira_value_pattern = r'LIRAMappingWrapper\([^,]+,\s*([^,]+),.*?\);'
    
    results = {}
    line_items = []
    
    try:
        with open(file_path, 'r', encoding='utf-8') as file:
            lines = file.readlines()
            
        i = 0
        while i < len(lines):
            line = lines[i]
            line_num = i + 1
            line_stripped = line.strip()
            
            # Skip empty lines
            if not line_stripped:
                i += 1
                continue
                
            # Skip commented lines (entire line commented out)
            if line_stripped.startswith('//'):
                i += 1
                continue
            
            # Check if this line starts with target fuse equation types
            is_target_line = (
                line_stripped.startswith('Fuses.Direct') or 
                line_stripped.startswith('Fuses.Virtual') or 
                line_stripped.startswith('LIRAMappingWrapper')
            )
            
            if is_target_line:
                # Collect multi-line statement until semicolon
                complete_statement = line_stripped
                start_line_num = line_num
                statement_lines = [line_num]
                
                # Continue reading lines until we find a semicolon or reach end of file
                j = i + 1
                while j < len(lines) and ';' not in complete_statement:
                    next_line = lines[j].strip()
                    # Skip empty lines within the statement
                    if next_line:
                        # Remove inline comments (// comments at end of line)
                        if '//' in next_line:
                            # Find the comment, but be careful not to break quoted strings
                            comment_pos = next_line.find('//')
                            # Simple check - if // is not within quotes, remove comment
                            if comment_pos != -1:
                                # Count quotes before the comment to see if we're inside a string
                                quotes_before = next_line[:comment_pos].count('"')
                                if quotes_before % 2 == 0:  # Even number of quotes means we're outside strings
                                    next_line = next_line[:comment_pos].strip()
                        
                        if next_line:  # Only add non-empty lines
                            complete_statement += " " + next_line
                            statement_lines.append(j + 1)
                    j += 1
                
                # Process the complete multi-line statement
                line_span = f"{start_line_num}" if len(statement_lines) == 1 else f"{start_line_num}-{statement_lines[-1]}"
                # Process the complete multi-line statement
                line_span = f"{start_line_num}" if len(statement_lines) == 1 else f"{start_line_num}-{statement_lines[-1]}"
                
                # Extract lineItem attributes from the complete statement
                lineitem_matches = re.findall(lineitem_pattern, complete_statement)
                
                # Extract fuse name
                fuse_name = "NA"
                if complete_statement.startswith('Fuses.Direct') or complete_statement.startswith('Fuses.Virtual'):
                    fuse_match = re.search(fuse_name_pattern, complete_statement)
                    if fuse_match:
                        fuse_name = f"Fuses.{fuse_match.group(1)}.{fuse_match.group(2)}"
                elif complete_statement.startswith('LIRAMappingWrapper'):
                    lira_match = re.search(lira_value_pattern, complete_statement)
                    if lira_match:
                        fuse_name = lira_match.group(1).strip()
                
                # Extract assigned value from complete statement
                assigned_value = "NA"
                if 'FuseSetValue' in complete_statement:
                    value_match = re.search(value_pattern, complete_statement, re.DOTALL)
                    if value_match:
                        assigned_value = value_match.group(1).strip()
                elif 'FuseBinaryValue' in complete_statement:
                    binary_value_match = re.search(binary_value_pattern, complete_statement, re.DOTALL)
                    if binary_value_match:
                        assigned_value = binary_value_match.group(1).strip()
                elif complete_statement.startswith('LIRAMappingWrapper'):
                    # For LIRAMappingWrapper, the value is the first parameter
                    lira_param_match = re.search(r'LIRAMappingWrapper\(([^,]+),', complete_statement)
                    if lira_param_match:
                        assigned_value = lira_param_match.group(1).strip()
                
                # Process lineItem attributes
                if lineitem_matches:
                    # Remove duplicates within the same statement while preserving order
                    unique_matches = []
                    seen = set()
                    for match in lineitem_matches:
                        if match not in seen:
                            unique_matches.append(match)
                            seen.add(match)
                    lineitem_attributes = unique_matches
                else:
                    # No lineItem attributes found, set as ["NA"]
                    unique_matches = []
                    lineitem_attributes = ["NA"]
                
                # Determine the fuse type
                if complete_statement.startswith('Fuses.Direct'):
                    fuse_type = 'Direct'
                elif complete_statement.startswith('Fuses.Virtual'):
                    fuse_type = 'Virtual'
                elif complete_statement.startswith('LIRAMappingWrapper'):
                    fuse_type = 'LIRAMapping'
                else:
                    fuse_type = 'Unknown'
                
                results[start_line_num] = {
                    'line': complete_statement,
                    'items': lineitem_attributes,  # Unique items per statement or ["NA"]
                    'unique_items': lineitem_attributes,  # Same as items now
                    'original_matches': lineitem_matches,  # Keep original matches for reference
                    'fuse_type': fuse_type,
                    'fuse_name': fuse_name,
                    'assigned_value': assigned_value,
                    'line_span': line_span  # Single line number or range
                }
                
                # Add to line_items only if there are actual lineItem attributes
                if lineitem_matches:
                    line_items.extend(unique_matches)
                
                # Skip the lines we've already processed
                i = j
            else:
                i += 1
        
        return {
            'line_details': results,
            'unique_items': sorted(list(set(line_items))),  # Unique items across all file (excluding "NA")
            'all_occurrences': line_items,  # All occurrences (now deduplicated per line, excluding "NA")
            'total_unique_count': len(set(line_items)),
            'total_occurrence_count': len(line_items)
        }
    except Exception as e:
        print(f"Error reading file: {e}")
        return None

def analyze_single_line(code_line):
    """
    Analyze a single line of code for lineItem attributes
    
    Args:
        code_line (str): Single line of C# code
        
    Returns:
        dict: Analysis results
    """
    items = extract_line_items_from_text(code_line)
    
    return {
        'original_line': code_line,
        'extracted_items': items,
        'count': len(items)
    }

def save_results_to_excel(file_results, output_path=None):
    """
    Save lineItem extraction results to Excel file with single comprehensive sheet
    
    Args:
        file_results (dict): Results from extract_line_items_from_file
        output_path (str): Optional output file path
        
    Returns:
        str: Path to the saved Excel file
    """
    if not file_results:
        print("❌ No results to save")
        return None
    
    # Generate timestamped filename if no output path provided
    if not output_path:
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        # Save to fuse_report folder
        output_dir = Path(__file__).parent / "fuse_report"
        output_dir.mkdir(exist_ok=True)  # Create directory if it doesn't exist
        output_path = output_dir / f"CS_file_extraction_results_{timestamp}.xlsx"
        output_path = str(output_path)  # Convert to string for compatibility
    
    try:
        # Single comprehensive sheet: All occurrences with complete information
        comprehensive_data = []
        
        for line_num, details in file_results['line_details'].items():
            # Create one row per statement (can be multi-line)
            line_items_str = ', '.join(details['items'])  # Unique items per statement or "NA"
            
            comprehensive_data.append({
                'Line_Number': details.get('line_span', line_num),  # Line span (single or range)
                'Fuse_Type': details.get('fuse_type', 'Unknown'),  # Fuse equation type
                'Fuse_Name': details.get('fuse_name', 'NA'),  # Extracted fuse name
                'LineItem_Attributes': line_items_str,  # Unique attributes per statement or "NA"
                'Attribute_Count': len([item for item in details['items'] if item != 'NA']),  # Count excluding NA
                'Assigned_Value': details.get('assigned_value', 'NA'),  # Extracted assigned value
                'Complete_Code_Line': details['line'],  # Full multi-line statement
                'Original_Matches': ', '.join(details.get('original_matches', [])) if details.get('original_matches') else 'None',  # Show what was originally found
                'Duplicates_Removed': 'Yes' if len(details.get('original_matches', [])) != len([item for item in details['items'] if item != 'NA']) else 'No'
            })
        
        df_comprehensive = pd.DataFrame(comprehensive_data)
        
        # Write to Excel with single sheet
        with pd.ExcelWriter(output_path, engine='xlsxwriter') as writer:
            # Write data to single sheet
            df_comprehensive.to_excel(writer, sheet_name='All_Occurrences', index=False)
            
            # Get workbook and worksheet for formatting
            workbook = writer.book
            worksheet = writer.sheets['All_Occurrences']
            
            # Define formats
            header_format = workbook.add_format({
                'bold': True,
                'text_wrap': True,
                'valign': 'top',
                'bg_color': '#D7E4BC',
                'border': 1,
                'font_size': 11
            })
            
            cell_format = workbook.add_format({
                'text_wrap': True,
                'valign': 'top',
                'border': 1,
                'font_size': 10
            })
            
            # Format columns
            worksheet.set_column('A:A', 12)  # Line_Number
            worksheet.set_column('B:B', 15)  # Fuse_Type
            worksheet.set_column('C:C', 50)  # Fuse_Name
            worksheet.set_column('D:D', 80)  # LineItem_Attributes
            worksheet.set_column('E:E', 15)  # Attribute_Count
            worksheet.set_column('F:F', 30)  # Assigned_Value
            worksheet.set_column('G:G', 150) # Complete_Code_Line (very wide for full lines)
            worksheet.set_column('H:H', 60)  # Original_Matches
            worksheet.set_column('I:I', 15)  # Duplicates_Removed
            
            # Set row height for better readability
            worksheet.set_default_row(25)
        
        print(f"✅ Results saved to Excel: {output_path}")
        print(f"📊 Single comprehensive sheet created:")
        print(f"   • All_Occurrences: {len(df_comprehensive)} fuse statements (single-line and multi-line)")
        print(f"   • Includes ALL target fuse statements (with and without lineItems)")
        print(f"   • Shows complete fuse equations, lineItem attributes, and assigned values")
        print(f"   • Multi-line statements are captured entirely until semicolon")
        print(f"   • Statements without lineItems marked as 'NA'")
        print(f"   • Excludes commented lines only")
        
        return output_path
        
    except Exception as e:
        print(f"❌ Error saving to Excel: {e}")
        return None

# Test with your example
def extract_info_from_cs_file():
    # Your original example line
    example_code = '''LIRAMappingWrapper(lineItem.MEM_BUS_SPD_UNLOCK_IND.Value, Fuses.Direct.Pcu.PCODE_SST_PP_4_DMFC, new Dictionary<string, string> { { "ENABLED", "7'h0" }, { "DISABLED", dec2hex(Convert.ToDouble(Math.Max(lineItem.MCR_FREQ.Value, lineItem.SSTPP4_DDR_FREQ.Value) / 200)) } });'''
    
    # New FuseBinaryValue example
    binary_example = '''Fuses.Direct.Pcu.PCODE_BRANDSTRING_CHAR_16.FuseBinaryValue = lineItem.CPU_BRAND_STRING.Value.Length >= 17 ? ASCII_Convertor_in_binary(lineItem.CPU_BRAND_STRING.Value.Substring(16, 1), 8) : "00000000";'''
    
    print("🔍 ANALYZING SINGLE LINES:")
    print("=" * 50)
    
    print("📄 Original LIRAMappingWrapper line:")
    result1 = analyze_single_line(example_code)
    print(f"Line: {result1['original_line'][:100]}...")
    print(f"Extracted Items: {result1['extracted_items']}")
    print(f"Count: {result1['count']}")
    
    print("\n📄 New FuseBinaryValue line:")
    result2 = analyze_single_line(binary_example)
    print(f"Line: {result2['original_line'][:100]}...")
    print(f"Extracted Items: {result2['extracted_items']}")
    print(f"Count: {result2['count']}")
    
    # Test with extract_line_items_from_file logic for the binary example
    print("\n🔍 TESTING FUSE PATTERN EXTRACTION:")
    print("=" * 50)
    import re
    lineitem_pattern = r'lineItem\.([a-zA-Z0-9_][a-zA-Z0-9_]*)'
    fuse_name_pattern = r'Fuses\.(Direct|Virtual)\.(.+?)\.(FuseSetValue|FuseBinaryValue)'
    binary_value_pattern = r'FuseBinaryValue\s*=\s*([^;]+);'
    
    lineitem_matches = re.findall(lineitem_pattern, binary_example)
    fuse_match = re.search(fuse_name_pattern, binary_example)
    binary_value_match = re.search(binary_value_pattern, binary_example)
    
    print(f"LineItem matches: {lineitem_matches}")
    if fuse_match:
        print(f"Fuse name: Fuses.{fuse_match.group(1)}.{fuse_match.group(2)}")
        print(f"Fuse type: {fuse_match.group(3)} (FuseBinaryValue)")
    if binary_value_match:
        print(f"Assigned value: {binary_value_match.group(1).strip()}")
    
    print("\n🔍 ANALYZING ENTIRE FILE:")
    print("=" * 50)
    
    # Analyze the C# file - use absolute path
    file_path = Path(__file__).parent / "fuse_files" / "CPU_GRANITE_RAPIDS_COMPUTE_DIE_M_Rule_org - Copy.cs"
    print(f"Looking for file at: {file_path}")
    
    if file_path.exists():
        file_results = extract_line_items_from_file(str(file_path))
        
        if file_results:
            print(f"📊 Found {file_results['total_unique_count']} unique lineItem attributes")
            print(f"📊 Total code lines processed: {len(file_results['line_details'])}")
            print(f"📊 Lines with lineItem attributes: {len([d for d in file_results['line_details'].values() if 'NA' not in d['items']])}")
            print(f"📊 Lines without lineItem attributes: {len([d for d in file_results['line_details'].values() if 'NA' in d['items']])}")
            print(f"📊 Total lineItem occurrences: {file_results['total_occurrence_count']} (excluding NA)")
            
            # Count by fuse type
            fuse_type_counts = {}
            for details in file_results['line_details'].values():
                fuse_type = details.get('fuse_type', 'Unknown')
                fuse_type_counts[fuse_type] = fuse_type_counts.get(fuse_type, 0) + 1
            
            print(f"\n📊 CODE LINES BREAKDOWN:")
            for fuse_type, count in sorted(fuse_type_counts.items()):
                print(f"   • {fuse_type}: {count} lines")
            
            # Show first 20 items
            for i, item in enumerate(file_results['unique_items'][:20], 1):
                # Count total occurrences of this item
                item_count = file_results['all_occurrences'].count(item)
                print(f"  {i:2d}. {item} ({item_count} occurrences)")
            
            if len(file_results['unique_items']) > 20:
                print(f"  ... and {len(file_results['unique_items']) - 20} more items")
            
            # Show some examples of code lines containing lineItems
            print(f"\n📋 SAMPLE CODE LINES (with and without lineItems):")
            print("=" * 70)
            count = 0
            for line_num, details in file_results['line_details'].items():
                if count >= 5:  # Show only first 5 examples
                    break
                print(f"Line {line_num} [{details.get('fuse_type', 'Unknown')}]:")
                print(f"  Fuse: {details.get('fuse_name', 'NA')}")
                print(f"  LineItems: {details['items']} ({len([item for item in details['items'] if item != 'NA'])} attributes)")
                print(f"  Value: {details.get('assigned_value', 'NA')}")
                if 'original_matches' in details and len(details['original_matches']) != len([item for item in details['items'] if item != 'NA']):
                    print(f"  Original matches: {details['original_matches']} (deduplicated)")
                print(f"  Code: {details['line'][:100]}...")
                print()
                count += 1
            
            # Save results to Excel
            print(f"\n💾 SAVING TO EXCEL:")
            print("=" * 50)
            excel_path = save_results_to_excel(file_results)
            if excel_path:
                print(f"📁 File saved as: {excel_path}")
                return excel_path
            
        else:
            print("❌ Failed to analyze file")
            return -1
    else:
        print(f"❌ File not found: {file_path}")
        return -1

if __name__ == "__main__":
    extract_info_from_cs_file()
