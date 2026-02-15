import json
data = json.load(open("resources/.file_metadata.json", "r"))
print(f"Files: {len(data.get('files', []))}")
for f in data["files"]:
    print(f"  {f.get('file_name')}: processed={f.get('processed')}, chunks={f.get('chunks_created')}")
