"""Phase 0 step 2: labels by text and context alone, fixed before the heard test runs.

    python plans/backing-vocal-lines/labels.py plans/backing-vocal-lines/out

Writes out/labels.json {label_key: label} and checks every label names an inventory text.
"""

import json
import sys
from pathlib import Path

DIRECTION = """
acoustic guitar playing|ad libs|aircraft engine rumbling|applauding|backstreet boys scream|
barking|basketball thudding|bass and drums|beat boxing|bell rings|birds calling|birds chirping|
birds screeching|birds squawking|bowie voice|brian screams in horror|brian startles agitatedly|
bring it all back by s club 7|bubbles popping|camera clicks|car screeches|car screeching|
cars humming|cars screeching|cars whirring|cd clicks|change clatters|chattering|cheerful music|
cheering|children laughing|chorus sings in foreign language|chuckling|chuffing and squawking|
clears throat|clock ticking|congas playing|creepy music|crowd chanting|crowd chattering|
crowd cheering|crowd cheering and clapping|crowd yelling|demon cackles|distorted music|
doors creak open|dramatic music|dramatic pop music|dramatic whooshing|drums beating|
dwayne laughing|electric guitar solo|electricity crackles|elephant trumpeting|
energetic guitar music|energetic rock music|falsetto|feet scraping|fireworks cracking|
fist pounds|flute playing|foot tapping|for good by kristin chenoweth and idina menzel|
french style laugh|genie in a bottle by christina aguilera|gentle bells|gentle guitar music|
gentle music|gentle music and humming|gentle piano solo|gentle pop music|giggles|
girls vocalizing|glass shattering|glass tinkling|groans|ground rumbling|grunts softly|guitar|
guitar playing|guitar strumming|haunting organ music|horses neighing|humming continues|hums|
i want it that way|instrumental interlude|intense music|intro beaming|jack shouts|jack shushing|
jack sings in vocalese|jc blowing|jemaine groaning pleasurably|jemaine whispers|justin laughing|
kyle huffs|laughing|laughs|like you used to do|lisa singing in spanish|lively music|
man singing in foreign language|melancholy piano music|mouthing|mouthing notes|music continues|
music ends|music fades|music stops|my love|normal voice|pandemonious banter|parrot squawking|
passersby talk indistinctly|passersby talking indistinctly|pencil tapping|phone clicks|
phone ringing|piano music|piano music continues|piano plays slow gentle melody|plane roaring|
pop music playing|purring|radio crackling|record halts|record scratch|record scratching|
relaxing music|relaxing music continues|rhythmic piano solo|roaring trumpeting|saxophone playing|
screen whooshing|seabirds calling|ship humming|shrieks|singer vocalizing|singing|
singing through vocoder|siren wailing|slow music|slow quiet electric guitar|
slow quiet piano music|slow rock music|sneezes|snorting|snorts|soft cymbal crash|
soft music begins|soft pop music|soft rock music|solemn piano music|song ends|soothing music|
speaking in foreign language|sputtering springing|squawking|static buzzing|students running|
synth strings and pop beat|synthesized voice|techno music playing|tempo picks up|thunder crashes|
thunder crashing|trumpets buzzing|upbeat groovy music|upbeat instrumental music|upbeat music|
upbeat music continues|upbeat music playing|upbeat pop music|violin music|
violin music continues|vocalizing|voices distorting|warm rhythmic music|
warm rhythmic music continues|waves lapping|whispering|whistling|whoosh|wild guitar music|
wild guitar music continues|wind whirring|wonderboy by tenacious d|words typing and beeping
"""
UNSURE = "beep|censored|heartbeat|skate"


def split(block: str) -> set[str]:
    return {k.strip() for k in block.replace("\n", "").split("|") if k.strip()}


def main(out: Path) -> None:
    keys = {row["label_key"] for row in json.loads((out / "inventory.json").read_text())}
    direction, unsure = split(DIRECTION), split(UNSURE)
    unknown = (direction | unsure) - keys
    assert not unknown, f"labels for texts not in the inventory: {sorted(unknown)}"
    assert not direction & unsure
    labels = {
        k: "direction" if k in direction else "unsure" if k in unsure else "sung" for k in keys
    }
    (out / "labels.json").write_text(json.dumps(labels, indent=1, sort_keys=True))
    for label in ("sung", "direction", "unsure"):
        print(label, sum(v == label for v in labels.values()))


if __name__ == "__main__":
    main(Path(sys.argv[1]))
