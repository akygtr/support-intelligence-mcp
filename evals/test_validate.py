from src.validate import validate_diagnosis

cases = {
    "clean": "The root cause is channel saturation. Slack confirms the tag "
             "count rose from 800 to 4000 without splitting the channel, which "
             "exceeds scan capacity and causes the dropped reads described in "
             "the ticket. Splitting the channel should resolve it.",
    "leaks email": "Contact carlos@opcsystems.com about the gateway issue. The "
                   "root cause is a certificate mismatch on the client trust "
                   "store, per the Slack discussion referenced in the ticket.",
    "has headers": "## Diagnosis\n\nChannel saturation caused by a tag count "
                   "increase from 800 to 4000 without splitting, which exceeds "
                   "the configured scan capacity for that channel.",
    "too short": "Channel saturation.",
}

for label, text in cases.items():
    r = validate_diagnosis(text)
    status = "PASS" if r.ok else "FAIL"
    detail = "; ".join(r.leaks + r.issues)
    print(f"{status:<5} {label:<12} {detail}")
