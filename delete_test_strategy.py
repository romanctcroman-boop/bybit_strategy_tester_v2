import httpx

# Delete strategy ID=1
r = httpx.delete("http://localhost:8000/api/v1/strategies/1")
print(f"DELETE /strategies/1: {r.status_code}")
if r.status_code in (200, 204):
    print("✅ Strategy deleted")
elif r.status_code == 404:
    print("Strategy already deleted or doesn't exist")
else:
    print(f"Error: {r.text}")
