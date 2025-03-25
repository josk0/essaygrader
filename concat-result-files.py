import os
import pandas as pd
import glob

OUTPUT_DIR = "./outputs"
CONCAT_FILE = "./outputs/combined.csv"

def concat_csv_files(directory_path, output_file):
    """
    Reads all CSV files from a directory, concatenates them,
    and saves the result as a CSV file.
    
    Args:
        directory_path: Path to the directory containing CSV files
        output_file: Path where the concatenated CSV will be saved
    
    Returns:
        DataFrame with the concatenated data
    """
    # Get list of all CSV files in the directory
    csv_files = glob.glob(os.path.join(directory_path, "*.csv"))
    
    if not csv_files:
        raise ValueError(f"No CSV files found in {directory_path}")
    
    # Read all CSV files and store in a list
    df_list = [pd.read_csv(file) for file in csv_files]
    
    # Concatenate all dataframes at once
    combined_df = pd.concat(df_list, ignore_index=True)
    
    # Save the combined dataframe to CSV
    combined_df.to_csv(output_file, index=False)
    
    return combined_df

concat_csv_files(directory_path=OUTPUT_DIR, output_file=CONCAT_FILE)