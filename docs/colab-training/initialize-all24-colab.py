"""Initialize all24 training with the current engine and fresh runtime identities."""
import argparse
import json
from pathlib import Path
import sys

# Supports both the repository location and a copy alongside the recipe in .scratch/.
script = Path(__file__).resolve()
root = next(parent for parent in script.parents if (parent / 'offline').is_dir())
sys.path.insert(0, str(root))
from offline.evolution import initialize
from offline.proposals import ProposalPolicy
from offline.registry import Entry, default_catalog

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--output', type=Path, default=Path('.scratch/all24-training-colab'))
parser.add_argument('--profile', choices=('all24', 'balanced', 'simple-focused'), default='all24',
                    help='Fresh immutable recipe; never changes an existing run.')
args = parser.parse_args()
recipe_name = args.profile + '-colab-setup.json'
recipe = json.loads(Path(__file__).with_name(recipe_name).read_text())
catalog, snapshot = default_catalog()
parent = Entry.local(
    args.profile + '-initial', module='omok.player', factory='IterativePlayer',
    options={'candidate_configuration': recipe['configuration']},
    source_paths=('omok', 'players', 'configs'), origin='local-engine', family='omok',
    acknowledgment='Local AI-written engine', variant=args.profile + '-training-initial',
    diagnostics=('search',),
    limitations='Current-source experimental evaluator; playing strength unverified.')
for name in recipe['policy']['screening']['opponents']:
    if catalog[name].data['availability'] != 'ready':
        raise SystemExit('Required training opponent unavailable: ' + name)
policy = recipe['policy'] | {'proposal': ProposalPolicy.for_parent(parent, **recipe['mutation']).data}
state = initialize(args.output, incumbent=parent, policy=policy, snapshot=snapshot)
print(json.dumps({'output': str(args.output), 'runtime': sys.version,
                  'profile': args.profile, 'recipe': recipe_name,
                  'incumbent': parent.identity, 'loader': parent.data['loader'],
                  'weights': len(recipe['configuration']['evaluation']['coefficients']),
                  'groups': recipe['mutation']['groups'], 'games_started': 0}))
