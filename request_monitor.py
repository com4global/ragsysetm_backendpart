"""
Real-time UI Request Monitor
Intercepts and logs all requests/responses between frontend and backend
"""

import json
from datetime import datetime
from pathlib import Path

# Color codes
GREEN = '\033[92m'
RED = '\033[91m'
YELLOW = '\033[93m'
BLUE = '\033[94m'
CYAN = '\033[96m'
RESET = '\033[0m'

class RequestMonitor:
    def __init__(self):
        self.requests = []
        self.log_file = Path("request_monitor.log")
    
    def log_request(self, method, endpoint, payload, timestamp=None):
        """Log incoming request"""
        if timestamp is None:
            timestamp = datetime.now()
        
        request_data = {
            "type": "REQUEST",
            "method": method,
            "endpoint": endpoint,
            "payload": payload,
            "timestamp": timestamp.isoformat()
        }
        
        self.requests.append(request_data)
        self._print_request(request_data)
        self._write_to_file(request_data)
    
    def log_response(self, status_code, response_data, timestamp=None):
        """Log outgoing response"""
        if timestamp is None:
            timestamp = datetime.now()
        
        response_data_obj = {
            "type": "RESPONSE",
            "status_code": status_code,
            "data": response_data,
            "timestamp": timestamp.isoformat()
        }
        
        self.requests.append(response_data_obj)
        self._print_response(response_data_obj)
        self._write_to_file(response_data_obj)
    
    def log_error(self, error_message, endpoint, timestamp=None):
        """Log error"""
        if timestamp is None:
            timestamp = datetime.now()
        
        error_data = {
            "type": "ERROR",
            "endpoint": endpoint,
            "message": error_message,
            "timestamp": timestamp.isoformat()
        }
        
        self.requests.append(error_data)
        self._print_error(error_data)
        self._write_to_file(error_data)
    
    def _print_request(self, data):
        """Pretty print request"""
        print(f"\n{BLUE}{'='*70}{RESET}")
        print(f"{BLUE}📨 INCOMING REQUEST{RESET}")
        print(f"{BLUE}{'='*70}{RESET}")
        print(f"⏰ Time: {data['timestamp']}")
        print(f"🔵 Method: {data['method']}")
        print(f"📍 Endpoint: {data['endpoint']}")
        print(f"📦 Payload:")
        print(f"   {json.dumps(data['payload'], indent=2)}")
    
    def _print_response(self, data):
        """Pretty print response"""
        status_color = GREEN if data['status_code'] == 200 else RED
        
        print(f"\n{CYAN}{'='*70}{RESET}")
        print(f"{CYAN}📤 OUTGOING RESPONSE{RESET}")
        print(f"{CYAN}{'='*70}{RESET}")
        print(f"⏰ Time: {data['timestamp']}")
        print(f"{status_color}📊 Status: {data['status_code']}{RESET}")
        print(f"📋 Data:")
        print(f"   {json.dumps(data['data'], indent=2)}")
    
    def _print_error(self, data):
        """Pretty print error"""
        print(f"\n{RED}{'='*70}{RESET}")
        print(f"{RED}❌ ERROR OCCURRED{RESET}")
        print(f"{RED}{'='*70}{RESET}")
        print(f"⏰ Time: {data['timestamp']}")
        print(f"📍 Endpoint: {data['endpoint']}")
        print(f"🚨 Error: {data['message']}")
    
    def _write_to_file(self, data):
        """Write log to file"""
        with open(self.log_file, 'a') as f:
            f.write(json.dumps(data) + "\n")
    
    def print_summary(self):
        """Print request/response summary"""
        print(f"\n{YELLOW}{'='*70}{RESET}")
        print(f"{YELLOW}MONITORING SUMMARY{RESET}")
        print(f"{YELLOW}{'='*70}{RESET}")
        
        total = len(self.requests)
        requests = sum(1 for r in self.requests if r['type'] == 'REQUEST')
        responses = sum(1 for r in self.requests if r['type'] == 'RESPONSE')
        errors = sum(1 for r in self.requests if r['type'] == 'ERROR')
        
        print(f"Total events: {total}")
        print(f"  ✅ Requests: {requests}")
        print(f"  📤 Responses: {responses}")
        print(f"  ❌ Errors: {errors}")
        print(f"\nLog saved to: {self.log_file}")

# Global monitor instance
monitor = RequestMonitor()

def add_monitoring_to_main_py():
    """
    Instructions for adding monitoring to main.py
    """
    code = '''
# Add this to main.py at the top
from request_monitor import monitor

# Add this middleware to log all requests/responses
@app.middleware("http")
async def monitor_requests(request, call_next):
    """Log all HTTP requests and responses"""
    
    # Log incoming request
    body = await request.body()
    if body:
        try:
            payload = json.loads(body)
        except:
            payload = str(body)
    else:
        payload = {}
    
    monitor.log_request(
        method=request.method,
        endpoint=str(request.url.path),
        payload=payload
    )
    
    # Process request
    response = await call_next(request)
    
    # Log response
    try:
        response_body = b""
        async for chunk in response.body_iterator:
            response_body += chunk
        
        try:
            response_data = json.loads(response_body)
        except:
            response_data = str(response_body)
        
        monitor.log_response(
            status_code=response.status_code,
            response_data=response_data
        )
        
        # Return response with body
        from fastapi.responses import Response
        return Response(
            content=response_body,
            status_code=response.status_code,
            headers=dict(response.headers),
            media_type=response.media_type
        )
    except Exception as e:
        monitor.log_error(
            error_message=str(e),
            endpoint=str(request.url.path)
        )
        return response

# Add import at top of main.py
import json
'''
    
    print("\n📝 To enable request monitoring, add this code to main.py:\n")
    print(code)

# Example usage
def example_monitoring():
    """Example of how to use the monitor"""
    
    print(f"\n{BLUE}{'='*70}{RESET}")
    print(f"{BLUE}EXAMPLE: Request/Response Monitoring{RESET}")
    print(f"{BLUE}{'='*70}{RESET}")
    
    # Simulate a request
    print("\n1️⃣ User types query in UI...")
    monitor.log_request(
        method="POST",
        endpoint="/chat",
        payload={"query": "What is the revenue in 2021?"}
    )
    
    # Simulate processing
    import time
    time.sleep(1)
    
    print("\n2️⃣ Backend processing...")
    print("   ├─ Embedding query...")
    time.sleep(0.5)
    print("   ├─ Searching vector store...")
    time.sleep(0.5)
    print("   ├─ Calling OpenAI LLM...")
    time.sleep(1)
    
    # Simulate a response
    print("\n3️⃣ Backend returns response...")
    monitor.log_response(
        status_code=200,
        response_data={
            "response": "The revenue in 2021 was €95,476 million.",
            "query": "What is the revenue in 2021?"
        }
    )
    
    # Print summary
    monitor.print_summary()

if __name__ == "__main__":
    # Show example
    example_monitoring()
    
    # Show how to add to main.py
    add_monitoring_to_main_py()
