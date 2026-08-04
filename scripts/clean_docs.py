import re
import json
import os
import glob
from pathlib import Path

from src.utils.logger import get_logger

logger = get_logger(__name__)


def extract_category(title_line):
    return title_line


def extract_ref(line):
    m = re.match(r'^Ref:\s*(.+)$', line.strip())
    return m.group(1) if m else None


def redact_phones(text):
    pattern = r'\+91[\s-]?\d{10}'
    matches = re.findall(pattern, text)
    return re.sub(pattern, '<REDACTED_PHONE>', text), len(matches)


def redact_emails(text):
    pattern = r'<[\w.+-]+@[\w.-]+\.\w+>|[\w.+-]+@[\w.-]+\.\w+'
    matches = re.findall(pattern, text)
    return re.sub(pattern, '<REDACTED_EMAIL>', text), len(matches)


def redact_names(text):
    count = 0
    result = text
    pattern = r'From:\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)'
    result, n = re.subn(pattern, lambda m: 'From: <REDACTED_NAME>', result)
    count += n
    name_only_pattern = r'(?<![@\w])([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)(?=\s+(?:spoke|said|reported|confirmed|noted|observed|mentioned|emailed|called|visited|notified|sent|wrote|forwarded|attended|reviewed|approved|denied|requested|suggested|informed|advised|recommended|proposed|escalated|flagged|raised|highlighted|discussed|presented|led|managed|coordinated|handled|prepared|submitted|authored|drafted|circulated|shared|distributed))'
    result, n = re.subn(name_only_pattern, '<REDACTED_NAME>', result)
    count += n
    return result, count


def redact_pii(text):
    stats = {"names": 0, "emails": 0, "phones": 0}
    text, n = redact_phones(text)
    stats["phones"] = n
    text, n = redact_emails(text)
    stats["emails"] = n
    text, n = redact_names(text)
    stats["names"] = n
    return text, stats


def compute_redaction_counts(names=0, emails=0, phones=0):
    return {"names": names, "emails": emails, "phones": phones, "total": names + emails + phones}


def extract_tags(text):
    tags = []
    if re.search(r'^SOP:', text, re.MULTILINE):
        tags.append("sop")
    if re.search(r'_Note:\s*attribution unverified', text):
        tags.append("attribution_unverified")
    return tags


def clean_empty_lines(text):
    text = re.sub(r'\n{3,}', '\n\n', text)
    text = text.strip()
    return text


def process_doc(filepath, content):
    doc_id = os.path.splitext(os.path.basename(filepath))[0]
    logger.debug("processing doc", extra={"file": filepath, "doc_id": doc_id, "content_length": len(content)})
    lines = content.split('\n')

    category = ""
    ref = None
    body_start = 0

    for i, line in enumerate(lines):
        stripped = line.strip()
        if re.match(r'^#\s+.+', stripped):
            category = extract_category(re.sub(r'^#\s+', '', stripped))
            body_start = i + 1
        elif re.match(r'^Ref:\s+', stripped) and ref is None:
            ref = extract_ref(stripped)
            body_start = i + 1

    body_lines = []
    for line in lines[body_start:]:
        s = line.strip()
        if s.startswith('#') or s.startswith('Ref:'):
            continue
        body_lines.append(line)

    raw_body = '\n'.join(body_lines)
    cleaned_body, redaction_stats = redact_pii(raw_body)
    cleaned_body = clean_empty_lines(cleaned_body)

    tags = extract_tags(content)

    attributes = {}
    from_match = re.search(r'^From:\s*<REDACTED_NAME>\s*<REDACTED_EMAIL>', cleaned_body, re.MULTILINE)
    if from_match:
        attributes["from"] = "REDACTED"

    result = {
        "id": doc_id,
        "text": cleaned_body,
        "metadata": {
            "category": category,
            "ref": ref or doc_id,
            "tags": tags,
            "attributes": attributes,
            "redactions": compute_redaction_counts(**redaction_stats),
        },
    }
    return result


def process_all_docs(input_dir, output_file):
    txt_files = sorted(glob.glob(os.path.join(input_dir, "*.txt")))
    logger.info("processing all docs", extra={"input_dir": input_dir, "file_count": len(txt_files), "output": output_file})
    records = []
    total_redactions = {"names": 0, "emails": 0, "phones": 0, "total": 0}

    for fpath in txt_files:
        with open(fpath, 'r', encoding='utf-8') as f:
            content = f.read()
        record = process_doc(fpath, content)
        records.append(record)
        r = record["metadata"]["redactions"]
        total_redactions["names"] += r["names"]
        total_redactions["emails"] += r["emails"]
        total_redactions["phones"] += r["phones"]
        total_redactions["total"] += r["total"]

    output_path = Path(output_file)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_file, 'w', encoding='utf-8') as f:
        for record in records:
            f.write(json.dumps(record, ensure_ascii=False) + '\n')

    logger.info("cleaning complete", extra={"doc_count": len(records), "output": output_file, "redactions": total_redactions})
    return records, total_redactions


if __name__ == "__main__":
    import sys
    input_dir = sys.argv[1] if len(sys.argv) > 1 else "Data/docs"
    output_file = sys.argv[2] if len(sys.argv) > 2 else "cleaned/cleaned_docs.jsonl"
    process_all_docs(input_dir, output_file)