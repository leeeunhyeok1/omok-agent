# AI-written by OpenAI Codex (GPT-6.1-sol), for issue #3.
"""Export visible user/assistant messages and tool records from a Codex session.

Internal reasoning, system/developer prompts, and runtime configuration are omitted.
Run again after the session to retain the final response and subsequent tool results.
"""
import argparse
import json
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source', type=Path, help='Codex session JSONL file')
    parser.add_argument('destination', type=Path)
    args = parser.parse_args()
    if args.source.resolve() == args.destination.resolve():
        parser.error('Source and destination must differ.')
    visible = []
    for line in args.source.read_text().splitlines():
        record = json.loads(line)
        if record.get('type') != 'response_item':
            continue
        payload = record['payload']
        kind = payload.get('type')
        if ((kind == 'message' and payload.get('role') in ('user', 'assistant'))
                or kind in ('function_call', 'function_call_output',
                            'custom_tool_call', 'custom_tool_call_output')):
            visible.append(record)
    args.destination.parent.mkdir(parents=True, exist_ok=True)
    args.destination.write_text(''.join(json.dumps(record, ensure_ascii=False) + '\n' for record in visible))
    print(f'Preserved {len(visible)} visible records.')


if __name__ == '__main__':
    main()
