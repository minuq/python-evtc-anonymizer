import argparse
import struct
import uuid
import zipfile
from collections import namedtuple
from pathlib import Path

agent_struct_format = "<QIIHHHHHH68s"
combat_struct_format = "<QQQIIIIHHHHBBBBBBBBBBBBL"

Header = namedtuple("Header", "date_magic revision boss junk agent_count")
header_struct = struct.Struct("<12sBHBI")
agent_struct = struct.Struct(agent_struct_format)
combat_struct = struct.Struct(combat_struct_format)


def ints_from_guid(guid: uuid.UUID):
    cg = guid.bytes_le
    dst_agent = int.from_bytes(cg[0:8], "little")
    value = int.from_bytes(cg[8:12], "little")
    buff_dmg = int.from_bytes(cg[12:16], "little")
    return dst_agent, value, buff_dmg


def guid_from_bytes(dst_agent: int, value: int, buff_dmg: int):
    db = dst_agent.to_bytes(8, "little")
    vb = value.to_bytes(4, "little")
    bdb = buff_dmg.to_bytes(4, "little")
    b = bytearray(
        [
            db[3],
            db[2],
            db[1],
            db[0],
            db[5],
            db[4],
            db[7],
            db[6],
            vb[0],
            vb[1],
            vb[2],
            vb[3],
            bdb[0],
            bdb[1],
            bdb[2],
            bdb[3],
        ]
    )
    return uuid.UUID(bytes=bytes(b))


ARENANET_GUID = uuid.UUID("4BBB52AA-D768-4FC6-8EDE-C299F2822F0F")
ANET_VALUES = ints_from_guid(ARENANET_GUID)


class Combat:
    def __init__(self, data: tuple):
        self.data = namedtuple(
            "Combat",
            "time src_agent dst_agent value buff_dmg i1 i2 i3 i4 i5 i6 i9 i10 i11 "
            "i12 i13 i14 i15 i16 state_change i17 i18 i19 p",
        )._make(data)
        self.src_agent = self.data.src_agent
        self.dst_agent = self.data.dst_agent
        self.value = self.data.value
        self.buff_dmg = self.data.buff_dmg
        self.state_change = self.data.state_change

    def tuple(self):
        return self.data._replace(
            dst_agent=self.dst_agent, value=self.value, buff_dmg=self.buff_dmg
        )


class Agent:
    def __init__(self, data: tuple):
        self.data = namedtuple("Agent", "a p i t c h hbw co hbh name")._make(data)
        self.address = self.data.a

        split = self.data.name.split(b"\x00")
        self.name = split[0]

        self.is_player = b":" in split[1]

        if self.is_player:
            self.character_name, self.account_name = (
                str(split[0], "utf-8"),
                str(split[1].replace(b":", b""), "utf-8"),
            )
            self.name_extra = split[2]

    def tuple(self):
        return self.data._replace(
            name=(
                bytes(
                    self.character_name + "\x00:" + self.account_name + "\x00", "utf-8"
                )
                + self.name_extra
            ).ljust(68, b"\x00")
        )


def read_zip(evtc_file: Path):
    with zipfile.ZipFile(evtc_file) as zf:
        bt = zf.read(evtc_file.stem)

    return bt


class Anon:
    def __init__(
        self, keep_pov: bool, evtc_file: str, keep_guilds: bool, compressed_output: bool
    ):
        self.evtc_file = Path(evtc_file)
        self.replace_guilds = keep_guilds
        self.compressed_output = compressed_output

        if zipfile.is_zipfile(self.evtc_file):
            self.evtc_data = read_zip(self.evtc_file)
        else:
            self.evtc_data = self.evtc_file.read_bytes()

        self.new_data = bytearray(self.evtc_data)

        self.header = Header._make(header_struct.unpack_from(self.evtc_data))

        assert (
            self.header.revision == 1
        ), "Only revision 1 logs are currently supported."

        self.pov = None
        self.keep_pov = keep_pov

        self.replace_guilds_and_find_pov()
        self.rename_agents()
        self.write()

    def replace_guilds_and_find_pov(self):
        # Skip after header and agents
        pointer = header_struct.size + self.header.agent_count * agent_struct.size

        # Read skill count and skip skills
        skill_count = struct.Struct("<I").unpack_from(
            self.evtc_data[pointer : pointer + 4]
        )[0]
        pointer += 4 + skill_count * 68

        guild_counter = 0 if self.replace_guilds else 10
        while pointer + 64 <= len(self.evtc_data):
            c = Combat(
                combat_struct.unpack_from(
                    self.evtc_data[pointer : pointer + combat_struct.size]
                )
            )
            if c.state_change == 29 and self.replace_guilds:
                c.dst_agent, c.value, c.buff_dmg = ANET_VALUES

                self.new_data[pointer : pointer + combat_struct.size] = struct.pack(
                    combat_struct_format, *c.tuple()
                )
                guild_counter += 1
            elif c.state_change == 13:
                self.pov = c.src_agent

            if guild_counter >= 10 and self.pov:
                break
            pointer += combat_struct.size

    def rename_agents(self):
        # Skip after header
        pointer = header_struct.size

        player_counter = 1
        for agent_id in range(self.header.agent_count):
            agent = Agent(
                agent_struct.unpack_from(
                    self.evtc_data[pointer : pointer + agent_struct.size]
                )
            )
            if agent.is_player:
                if self.keep_pov and agent.address == self.pov:
                    print(f"Skipping PoV: {agent.account_name}")
                    pointer += agent_struct.size
                    continue

                print(
                    f"Replacing {agent.account_name} with Anonymous {player_counter}.1234"
                )
                agent.account_name = f"Anonymous {player_counter}.1234"
                agent.character_name = f"Character {player_counter}"

                self.new_data[pointer : pointer + agent_struct.size] = struct.pack(
                    agent_struct_format, *agent.tuple()
                )

                player_counter += 1

            # Advance in data
            pointer += agent_struct.size

    def write(self):
        print("Writing file, this might take a while.")
        path = self.evtc_file.parent.absolute()
        name = self.evtc_file.stem + "-anonymized"
        if self.compressed_output:
            with zipfile.ZipFile(
                path / f"{name}.zevtc", "w", compression=zipfile.ZIP_BZIP2
            ) as zf:
                zf.writestr(name, self.new_data)

        else:
            (path / f"{name}.evtc").write_bytes(self.new_data)


def evtc_path(path: str):
    p = Path(path)
    if p.exists() and p.suffix in [".evtc", ".zevtc", ".evtc.zip"]:
        return p
    raise argparse.ArgumentError(f"File {p.absolute()} does not exist.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser("evtc")
    parser.add_argument(
        "evtc_file", metavar="evtc-file", help="Path to a .evtc file", type=evtc_path
    )
    parser.add_argument("--pov", help="Keep PoV (default: false)", action="store_true")
    parser.add_argument(
        "--uncompressed", "-U", help="Don't compress output file", action="store_false"
    )
    parser.add_argument(
        "--keep-guilds", "-G", help="Don't replace guild names", action="store_false"
    )

    args = parser.parse_args()
    Anon(
        keep_pov=args.pov,
        evtc_file=args.evtc_file,
        keep_guilds=args.keep_guilds,
        compressed_output=args.uncompressed,
    )
