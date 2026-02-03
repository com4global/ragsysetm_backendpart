from pinecone import Pinecone
import os

pc = Pinecone(api_key="pcsk_5pm3KX_P3re95Ea14EBoZrZ9yAuaUX9SFHusY2vKRKsdQPgEa54TyuqXVq48Tx5BPSx7et")
index_name = "hr-assistant-index"
index = pc.Index(index_name)

def verify_specific_file(filename):
    # Search for any chunk belonging to this filename
    # We use a dummy vector [0.0, 0.0, ...] because we only care about the metadata filter
    results = index.query(
        vector=[0.0] * 1536, # Use 1536 for OpenAI, or your specific dimension
        filter={"doc_name": {"$eq": filename}},
        top_k=5,
        include_metadata=True,
        namespace="pdf" # or "sharepoint"
    )
    
    if results['matches']:
        print(f"✅ Success! Found {len(results['matches'])} chunks for '{filename}'")
        for match in results['matches']:
            print(f" - Found on Page: {match['metadata'].get('page')}")
    else:
        print(f"❌ File '{filename}' not found in the database.")

def check_my_storage():
    stats = index.describe_index_stats()
    
    print(f"--- Index: {index_name} Stats ---")
    print(f"Total Vectors in DB: {stats['total_vector_count']}")
    
    print("\nBreakdown by Namespace:")
    for ns_name, ns_data in stats['namespaces'].items():
        print(f"📍 Namespace: '{ns_name}' | Vectors: {ns_data['vector_count']}")

if __name__ == "__main__":
    check_my_storage()
    verify_specific_file("youtube_8jPQjjsBbIc.txt")