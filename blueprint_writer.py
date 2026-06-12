# blueprint_writer.py — material mapping helpers for on-demand block generation

SHAPE_IDS = {
    "wood2": "1fc74a28-addb-451a-878d-c3c605d63811",
    "scrapmetal": "1f7ac0bb-ad45-4246-9817-59bdf7f7ab39",
    "metal2": "1016cafc-9f6b-40c9-8713-9019d399783f",
    "metal3": "c0dfdea5-a39d-433a-b94a-299345a5df46",
    "scrapstone": "30a2288b-e88e-4a92-a916-1edbfc2b2dac",
    "concrete2": "ff234e42-5da4-43cc-8893-940547c97882",
    "concrete3": "e281599c-2343-4c86-886e-b2c1444e8810",
    "crackedconcrete": "f5ceb7e3-5576-41d2-82d2-29860cf6e20e",
    "concretetiles": "cd0eff89-b693-40ee-bd4c-3500b23df44e",
    "metalbricks": "220b201e-aa40-4995-96c8-e6007af160de",
    "beam": "25a5ffe7-11b1-4d3e-8d7a-48129cbaf05e",
    "bubblewrap": "f406bf6e-9fd5-4aa0-97c1-0b3c2118198e",
    "plastic": "628b2d61-5ceb-43e9-8334-a4135566df7a",
    "insulation": "9be6047c-3d44-44db-b4b9-9bcf8a9aab20",
    "drywall": "b145d9ae-4966-4af6-9497-8fca33f9aee3",
    "carpet": "febce8a6-6c05-4e5d-803b-dfa930286944",
    "plasticwall": "e981c337-1c8a-449c-8602-1dd990cbba3a",
    "metalnet": "4aa2a6f0-65a4-42e3-bf96-7dec62570e0b",
    "crossnet": "3d0b7a6e-5b40-474c-bbaf-efaa54890e6a",
    "tryponet": "ea6864db-bb4f-4a89-b9ec-977849b6713a",
    "stripednet": "a479066d-4b03-46b5-8437-e99fec3f43ee",
    "squarenet": "b4fa180c-2111-4339-b6fd-aed900b57093",
    "restroom": "920b40c8-6dfc-42e7-84e1-d7e7e73128f6",
    "treadplate": "f7d4bfed-1093-49b9-be32-394c872a1ef4",
    "warehousefloor": "3e3242e4-1791-4f70-8d1d-0ae9ba3ee94c",
    "wornmetal": "d740a27d-cc0f-4866-9e07-6a5c516ad719",
    "spaceshipfloor": "4ad97d49-c8a5-47f3-ace3-d56ba3affe50",
    "sand": "c56700d9-bbe5-4b17-95ed-cef05bd8be1b",
    "armoredglass": "b5ee5539-75a2-4fef-873b-ef7c9398b3f5",
}

DEFAULT_SHAPE_ID = SHAPE_IDS["plastic"]
GLASS_SHAPE_ID = SHAPE_IDS["armoredglass"]


def get_shape_id_for_block(block_name):
    block_lower = block_name.lower()
    if any(
        wood in block_lower
        for wood in [
            "oak", "birch", "spruce", "jungle", "acacia", "dark_oak",
            "mangrove", "cherry", "crimson", "warped",
        ]
    ):
        return SHAPE_IDS["wood2"]
    return DEFAULT_SHAPE_ID


def rgba_to_hex(rgb):
    r, g, b = rgb[0], rgb[1], rgb[2]
    return f"{r:02x}{g:02x}{b:02x}".upper()
