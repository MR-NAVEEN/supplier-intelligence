"""Gold Q&A for catalogue chat. Prices come from extracted Finger + JBL PDFs."""

GOLD_CASES = [
    {
        'id': 'finger-soundking-price',
        'q': 'What is the MRP of SOUNDKING-5W?',
        'must': ['SOUNDKING-5W', '1499'],
        'must_not': ['1999', '6999'],
    },
    {
        'id': 'finger-minimot-price',
        'q': 'How much is MINIMOT-5W in the Finger catalogue?',
        'must': ['MINIMOT-5W', '1999'],
    },
    {
        'id': 'finger-soundnugget',
        'q': 'Price of Soundnugget 8W',
        'must': ['SOUNDNUGGET-8W', '1995'],
    },
    {
        'id': 'finger-musilicious',
        'q': 'What is MUSILICIOUS 3 priced at?',
        'must': ['MUSILICIOUS 3', '1175'],
    },
    {
        'id': 'finger-swag',
        'q': 'MRP of SWAG5-10W',
        'must': ['SWAG5-10W', '2999'],
    },
    {
        'id': 'finger-karaoke',
        'q': 'How much is KARAOKESTAR-K4-12W?',
        'must': ['KARAOKESTAR-K4-12W', '2999'],
    },
    {
        'id': 'finger-rocknroll',
        'q': 'Price of ROCK-N-ROLL H6',
        'must': ['ROCK-N-ROLL H6', '1999'],
    },
    {
        'id': 'finger-kickstar',
        'q': 'What is the price of KICKSTAR-C11?',
        'must': ['KICKSTAR-C11', '1645'],
    },
    {
        'id': 'finger-magpower',
        'q': 'MAGPOWER-P10 price',
        'must': ['MAGPOWER-P10', '3445'],
    },
    {
        'id': 'finger-fuel',
        'q': 'How much is FUEL K3 in Finger 2026?',
        'must': ['FUEL K3', '2199'],
    },
    {
        'id': 'finger-bt-freedom',
        'q': 'BT-FREEDOM MRP',
        'must': ['BT-FREEDOM', '1199'],
    },
    {
        'id': 'finger-holdmeup',
        'q': 'Price of HOLD-ME-UP3',
        'must': ['HOLD-ME-UP3', '499'],
    },
    {
        'id': 'finger-cheapest',
        'q': 'What is the cheapest product in the Finger catalogue?',
        'must': ['HOLD-ME-UP3', '499'],
        'must_not': ['3445'],
    },
    {
        'id': 'finger-expensive',
        'q': 'Most expensive Finger product?',
        'must': ['MAGPOWER-P10', '3445'],
    },
    {
        'id': 'finger-under-1500',
        'q': 'Finger products under 1500',
        'must': ['HOLD-ME-UP3', '499', 'MUSILICIOUS 3', '1175', 'BT-FREEDOM', '1199', 'SOUNDKING-5W', '1499'],
        'must_not': ['3445', '2999'],
    },
    {
        'id': 'finger-page-5',
        'q': 'What products are on page 5 of Finger?',
        'must': ['BT-FREEDOM', '1199', 'HOLD-ME-UP3', '499'],
    },
    {
        'id': 'finger-page-2',
        'q': 'List Finger page 2 products',
        'must': ['MUSILICIOUS 3', 'SWAG5-10W', 'KARAOKESTAR-K4-12W'],
    },
    {
        'id': 'finger-count',
        'q': 'How many products are in the Finger catalogue?',
        'must': ['12'],
    },
    {
        'id': 'jbl-wave-buds',
        'q': 'What is the price of JBL WAVE BUDS 2?',
        'must': ['WAVE BUDS 2', '6999'],
        'must_not': ['7499'],
    },
    {
        'id': 'jbl-wave-beam',
        'q': 'How much is WAVE BEAM 2?',
        'must': ['WAVE BEAM 2', '7499'],
        'must_not': ['6999'],
    },
    {
        'id': 'jbl-live-buds',
        'q': 'MRP of LIVE BUDS 3',
        'must': ['LIVE BUDS 3', '24999'],
    },
    {
        'id': 'jbl-live-beam',
        'q': 'Price of LIVE BEAM 3 in JBL',
        'must': ['LIVE BEAM 3', '24999'],
    },
    {
        'id': 'jbl-cheapest',
        'q': 'Cheapest JBL product?',
        'must': ['WAVE BUDS 2', '6999'],
        'must_not': ['24999'],
    },
    {
        'id': 'jbl-compare',
        'q': 'Compare WAVE BUDS 2 vs WAVE BEAM 2',
        'must': ['WAVE BUDS 2', '6999', 'WAVE BEAM 2', '7499'],
    },
    {
        'id': 'jbl-count',
        'q': 'How many JBL products were extracted?',
        'must': ['4'],
    },
    {
        'id': 'unknown-product',
        'q': 'What is the price of iPhone 16?',
        'must': ['do not see'],
        'must_not': ['1499', '6999'],
    },
    {
        'id': 'nl-soundking-watts',
        'q': 'sound king 5 watt price please',
        'must': ['SOUNDKING-5W', '1499'],
    },
    {
        'id': 'nl-hold-me-up',
        'q': 'whats hold me up 3 cost',
        'must': ['HOLD-ME-UP3', '499'],
    },
    {
        'id': 'nl-jbl-wave-buds',
        'q': 'jbl wave buds mrp',
        'must': ['WAVE BUDS 2', '6999'],
        'must_not': ['7499'],
    },
    {
        'id': 'nl-finger-cheapest',
        'q': 'which finger item is cheapest',
        'must': ['HOLD-ME-UP3', '499'],
    },
]
