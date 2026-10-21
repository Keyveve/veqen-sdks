# veqen (Python)

Official Python client for [Veqen](https://veqen-app.com): catch disposable emails, typos, datacenter and Tor IPs, and VoIP numbers with one API call.

```bash
pip install https://veqen-app.com/static/sdk/veqen-0.1.0-py3-none-any.whl
```

```python
from veqen import Veqen, VeqenError

client = Veqen()  # reads VEQEN_API_KEY from the environment

result = client.signup(email="jane@mailinator.com", ip="185.220.101.1")
print(result["risk"]["verdict"])        # "refuse"
for reason in result["risk"]["reasons"]:
    print(reason["code"], reason["message"])
```

| Method | Endpoint | Credits |
|---|---|---|
| `email(address, verify_mailbox=False)` | `/v1/email/check` | 1 (+5) |
| `emails(list)` | `/v1/email/batch` (chunks of 100) | 1 each |
| `ip(address)` | `/v1/ip/check` | 1 |
| `phone(number, country=None)` | `/v1/phone/check` | 1 |
| `domain(name)` | `/v1/domain/check` | 1 |
| `signup(email=, ip=, phone=, phone_country=)` | `/v1/signup/check` | 3 |
| `account()`, `usage(days=30)` | `/v1/account`, `/v1/usage` | 0 |

Errors raise `VeqenError` with `.status`, `.type` (e.g. `insufficient_credits`) and `.message`. Requests are retried on 429 and 5xx. Docs: https://veqen-app.com/docs
