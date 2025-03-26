from newspapers_scrap.config.config import env

# Paths to the files
alternate_names = "alternateNamesV2.txt"
alternate_names_clean = "alternateNamesV2_clean.txt"
patronymes = "patronymes.txt"
patronymes_clean = "patronymes_clean.txt"
fr_commons_dict = "fr_commons.txt"
output_dict = 'fr.txt'

alternate_names_path = env.storage.paths.dicts_dir + '/' + alternate_names
alternate_names_clean_path = env.storage.paths.dicts_dir + '/' + alternate_names_clean
patronymes_path = env.storage.paths.dicts_dir + '/' + patronymes
patronymes_clean_path = env.storage.paths.dicts_dir + '/' + patronymes_clean
fr_commons_path = env.storage.paths.models_dir + '/' + fr_commons_dict
path_dict_out = env.storage.paths.models_dir + '/' + output_dict

# Extract data from alternateNamesV2.txt
with open(alternate_names_path, "r", encoding="utf-8") as f_in, \
        open(alternate_names_clean_path, "w", encoding="utf-8") as f_out:
    for ligne in f_in:
        morceaux = ligne.strip().split('\t')
        if len(morceaux) > 3 and morceaux[2] == "fr":
            nom_fr = morceaux[3]
            f_out.write(nom_fr + "\n")

# Clean patronymes.txt
with open(patronymes_path, "r") as infile, open(patronymes_clean_path, "w") as outfile:
    for line in infile:
        nom = line.strip().split(",")[0]
        outfile.write(nom + "\n")

# Use a dictionary to track names and their frequencies
word_frequencies = {}

# Read names from alternateNamesV2_clean.txt
print(f"Reading names from {alternate_names_clean_path}...")
with open(alternate_names_clean_path, "r", encoding="utf-8") as f:
    for line in f:
        name = line.strip()
        if name:
            word_frequencies[name] = 1  # Default frequency

# Read names from patronymes_clean.txt
print(f"Reading names from {patronymes_clean_path}...")
with open(patronymes_clean_path, "r", encoding="utf-8") as f:
    for line in f:
        name = line.strip()
        if name:
            word_frequencies[name] = 1  # Default frequency

# Read existing names from output_dict and preserve frequencies
print(f"Reading existing names from {fr_commons_path}...")

with open(fr_commons_path, "r", encoding="utf-8") as f:
    for line in f:
        parts = line.strip().split()
        if parts and len(parts) >= 2:
            name = ' '.join(parts[:-1])
            try:
                frequency = int(parts[-1])
                word_frequencies[name] = frequency
            except ValueError:
                word_frequencies[line.strip()] = 1
        elif parts:
            word_frequencies[parts[0]] = 1

# Write the combined names to the output file
print(f"Writing {len(word_frequencies)} unique names to {path_dict_out}...")
with open(path_dict_out, "w", encoding="utf-8") as f:
    for name in sorted(word_frequencies.keys()):
        f.write(f"{name}\t{word_frequencies[name]}\n")

print(f"Dictionary created successfully at {path_dict_out}")
