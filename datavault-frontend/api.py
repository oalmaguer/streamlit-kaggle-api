import pandas as pd
import kaggle

# Authenticate with Kaggle
kaggle.api.authenticate()

# Download the dataset
print("Downloading dataset...")
kaggle.api.dataset_download_files('NUFORC/ufo-sightings', path='.', unzip=True)

# Read the scrubbed (cleaned) dataset
print("\nReading the dataset...")
df = pd.read_csv('scrubbed.csv')

# Display basic information about the dataset
print("\nDataset Info:")
print(df.info())

# Show the first few rows
print("\nFirst 5 rows of the dataset:")
print(df.head())