from datasets import load_dataset

# Load a dataset (can be cached automatically)
dataset = load_dataset("glue", "mrpc")

# Inspect the data
print(dataset["train"])  # Prints sample rows
print(dataset.column_names)  # Lists column names
