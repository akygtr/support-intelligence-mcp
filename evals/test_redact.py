from src.redact import redact

sample = {
    "records": [{
        "NAME": "Carlos Rivera",
        "EMAIL": "carlos@opcsystems.com",
        "PHONE": "555-123-4567",
        "COMPANY": "OPC Systems",
    }],
    "results": [{
        "text": "Reached out to dana.whitfield@northvale.example about the "
                "gateway at 192.168.4.22, token EXAMPLEONLYnotarealkey0123456789abcdef",
    }],
    "email": "someone@example.com",
}

import json
print(json.dumps(redact(sample), indent=2))
