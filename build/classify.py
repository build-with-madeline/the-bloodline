#!/usr/bin/env python3
"""
Assign every person a PRIMARY dynasty (their birth house) = which page they live on.

Method:
  1. Seed the figures I can identify by rule (regnal ids + house keywords).
  2. Propagate house membership through the family graph: an unassigned person
     inherits from an assigned parent, else child, else spouse. Iterated to fixpoint.

A union whose two parents have DIFFERENT primary dynasties is a BRIDGE: on each
parent's page the other parent renders as a linked bridge node. That is how the
intermarriages stitch the pages together.

Bucketing is heuristic v1 and is trivially correctable: edit SEED / OVERRIDE below
and regenerate. Nothing downstream hardcodes placement.
"""
import json
import sys
from pathlib import Path
from collections import defaultdict, Counter

sys.path.insert(0, str(Path(__file__).parent))
from model import load_merged

OUT = Path("/Users/madelinevinson/Downloads/the-bloodline/data/dynasty.json")

# Ordered dynasty list -> page order
DYNASTIES = [
    ("CAROLINGIAN", "Carolingians & Frankish Roots"),
    ("KIEV", "Kievan Rus"),
    ("HRE", "Holy Roman Empire"),
    ("FRANCE", "France — Capet, Valois & Guise"),
    ("IBERIA", "Iberia — Castile, Aragon & Portugal"),
    ("NORMANDY", "Normandy & the House of Wessex"),
    ("PLANTAGENET", "Plantagenet — Angevin, Lancaster & York"),
    ("TUDOR", "Tudor England"),
    ("SCOTLAND", "Scotland — Dunkeld, Bruce & Stewart"),
    ("MEDICI", "The Medici & Italy"),
    ("BYZANTIUM", "Byzantium & the East"),
    ("ANTIQUITY", "Rome & Antiquity"),
    ("SCRIPTURE", "Scripture & the Patriarchs"),
    ("SUMER", "The Kings of Sumer"),
]

# --- explicit id overrides (win over everything) ---
OVERRIDE = {
    # Kievan Rus
    "RURIK":"KIEV","IGOR":"KIEV","OLGA":"KIEV","SVIATOSLAV":"KIEV","VLADIMIR":"KIEV",
    "ROGNEDA":"KIEV","YAROSLAV":"KIEV","INGEGERD":"KIEV","ANNEKIEV":"KIEV",
    # Medici / Italy / Popes
    "GIOVANNIBICCI":"MEDICI","PICCARDABUERI":"MEDICI","COSIMOELDER":"MEDICI",
    "CONTESSINABARDI":"MEDICI","PIEROGOUTY":"MEDICI","LUCREZIATORNABUONI":"MEDICI",
    "LORENZOMAGNIFICENT":"MEDICI","CLARICEORSINI":"MEDICI","GIULIANOMEDICI":"MEDICI",
    "POPELEOX":"MEDICI","POPECLEMENTVII":"MEDICI","PIEROUNFORTUNATE":"MEDICI",
    "ALFONSINAORSINI":"MEDICI","LORENZOURBINO":"MEDICI","MADELEINEAUVERGNE":"MEDICI",
    "ALFONSOIESTE":"MEDICI","LUCREZIABORGIA":"MEDICI","ERCOLEII":"MEDICI","RENEEFR":"FRANCE",
    # Tudor
    "MAREDUDD":"TUDOR","OT":"TUDOR","EDT":"TUDOR","MARGB":"TUDOR","JB":"TUDOR",
    "HVII":"TUDOR","EOY":"TUDOR","HVIII":"TUDOR","ARTHUR":"TUDOR","MARGT":"TUDOR",
    "MARYTUDORWQ":"TUDOR","MARYI":"TUDOR","ELIZI":"TUDOR","EDVI":"TUDOR",
    "COA":"IBERIA","AB":"TUDOR","JANESEY":"TUDOR","ANNECLEVES":"HRE","CATHOWARD":"TUDOR","CATHPARR":"TUDOR",
    "THOMASB":"TUDOR","ELIZHOW":"TUDOR","JOHNSEY":"TUDOR","MARGWENT":"TUDOR",
    # Scotland (Dunkeld + Bruce + Stewart)
    "CRIN":"SCOTLAND","BETH":"SCOTLAND","DUNC":"SCOTLAND","DUNCW":"SCOTLAND",
    "MALCI":"SCOTLAND","KENNII":"SCOTLAND","MALCII":"SCOTLAND","MALC":"SCOTLAND",
    "MARGS":"SCOTLAND","INGIB":"SCOTLAND","DUNCII":"SCOTLAND",
    "ROBERTDEBRUS":"SCOTLAND","MARJORIECARRICK":"SCOTLAND","ROBERTBRUCE":"SCOTLAND",
    "ISABELMAR":"SCOTLAND","ELIZBURGH":"SCOTLAND","MARJORIEBRUCE":"SCOTLAND",
    "WALTERSTEWART":"SCOTLAND","MOG":"FRANCE","MOG_":"FRANCE",
    # early England / Wessex / Normandy
    "ALFREDGREAT":"NORMANDY","EDGARP":"NORMANDY","AELFTH":"NORMANDY","AETH":"NORMANDY",
    "AELF":"NORMANDY","EDMI":"NORMANDY","EALD":"NORMANDY","EDEX":"NORMANDY","AGA":"NORMANDY",
    "MARGS_":"SCOTLAND","AELFTHWESSEX":"NORMANDY",
    "ROLLO":"NORMANDY","POPPA":"NORMANDY","WLONGSWORD":"NORMANDY","SPROTA":"NORMANDY",
    "RICHI":"NORMANDY","GUNNOR":"NORMANDY","RICHII":"NORMANDY","JUDB":"NORMANDY",
    "RI":"NORMANDY","HERL":"NORMANDY","WTC":"NORMANDY","MOF":"NORMANDY",
    "ROBCURT":"NORMANDY","WADELIN":"NORMANDY","ADELA":"NORMANDY","STEPHENBLOIS":"NORMANDY",
    "STEPHENKING":"NORMANDY","HI":"NORMANDY","MOS":"SCOTLAND","EMPM":"NORMANDY","MATILDAPLANT":"NORMANDY",
    "BALD":"NORMANDY","ADELF":"FRANCE",
    "CHARLESBALD":"CAROLINGIAN","LOUISPIOUS":"CAROLINGIAN","LOTHAIRI":"CAROLINGIAN",
    "ARNULFMETZ":"CAROLINGIAN",
    "CHLODIO":"CAROLINGIAN","HILDEBURG":"CAROLINGIAN","PHARAMOND":"CAROLINGIAN","ARGOTTA":"CAROLINGIAN",
    "HERBERTIVERM":"CAROLINGIAN","HERBERTIVERMW":"CAROLINGIAN","PEPINVERMANDOIS":"CAROLINGIAN","PEPINVERMW":"CAROLINGIAN",
    "BERNARDITALY":"CAROLINGIAN","CUNIGUNDA":"CAROLINGIAN","PEPINITALY":"CAROLINGIAN","PEPINITALYW":"CAROLINGIAN","HILDEGARD":"CAROLINGIAN",
    "CONSTANTIUS2":"ANTIQUITY","CONSTANTIUS2W":"ANTIQUITY","CONSTANTINE1":"ANTIQUITY","FAUSTA":"ANTIQUITY",
    "CONSTANTIUSCHL":"ANTIQUITY","HELENA":"ANTIQUITY","CLAUDIUSGOTH":"ANTIQUITY","CLAUDIUSGOTHW":"ANTIQUITY",
    "OCTAVIA":"ANTIQUITY","ANTONIAMINOR":"ANTIQUITY","NERODRUSUS":"ANTIQUITY","CLAUDIUS":"ANTIQUITY",
    "GERMANICUS":"ANTIQUITY","AGRIPPINAELDER":"ANTIQUITY","AGRIPPINAYOUNGER":"ANTIQUITY","DOMITIUSAHEN":"ANTIQUITY",
    "NERO":"ANTIQUITY","GAIUSOCTAVIUS":"ANTIQUITY","ATIA":"ANTIQUITY","AUGUSTUS":"ANTIQUITY",
    "SEPTIMIUSSEV":"ANTIQUITY","JULIADOMNA":"ANTIQUITY",
    "BASSIANUS":"ANTIQUITY","HERODIANPR":"ANTIQUITY","SOHAEMUS":"ANTIQUITY","DRUSILLAMAUR":"ANTIQUITY",
    "PTOLEMYMAUR":"ANTIQUITY","PTOLEMYMAURW":"ANTIQUITY","JUBAII":"ANTIQUITY","CLEOSELENE":"ANTIQUITY",
    "CLEOPATRA7":"ANTIQUITY","MARKANTONY":"ANTIQUITY","PTOLEMY12":"ANTIQUITY","CLEOPATRA5":"ANTIQUITY",
    "PTOLEMY9":"ANTIQUITY","PT9CONC":"ANTIQUITY","PTOLEMY8":"ANTIQUITY","CLEOPATRA3":"ANTIQUITY",
    "PTOLEMY5":"ANTIQUITY","CLEOPATRA1":"ANTIQUITY","PTOLEMY4":"ANTIQUITY","ARSINOE3":"ANTIQUITY",
    "PTOLEMY3":"ANTIQUITY","BERENICE2":"ANTIQUITY","PTOLEMY2":"ANTIQUITY","ARSINOE1":"ANTIQUITY",
    "PTOLEMY1":"ANTIQUITY","BERENICE1":"ANTIQUITY","PHILIP2":"ANTIQUITY","ARSINOEMAC":"ANTIQUITY",
    "AMYNTAS3":"ANTIQUITY","EURYDICE1":"ANTIQUITY","ANTIOCHUS3":"ANTIQUITY","LAODICE3":"ANTIQUITY",
    "SELEUCUS2":"ANTIQUITY","LAODICE2":"ANTIQUITY","ANTIOCHUS2":"ANTIQUITY","LAODICE1":"ANTIQUITY",
    "ANTIOCHUS1":"ANTIQUITY","STRATONICE":"ANTIQUITY","SELEUCUS1":"ANTIQUITY","APAMA":"ANTIQUITY",
    "HERODAGRIPPA1":"ANTIQUITY","CYPROS":"ANTIQUITY","ARISTOBULUS4":"ANTIQUITY","BERENICEHEROD":"ANTIQUITY",
    "HERODGREAT":"ANTIQUITY","MARIAMNE":"ANTIQUITY","TIGRANES2":"ANTIQUITY","CLEOPATRAPONT":"ANTIQUITY",
    "THEOPHANU":"BYZANTIUM","ISAACANGELOS":"BYZANTIUM","IRENEANG":"BYZANTIUM",
    "MANUELEROTIKOS":"BYZANTIUM","MANUELWIFE":"BYZANTIUM","JOHNKOMNENOS":"BYZANTIUM","ANNADALASSENE":"BYZANTIUM",
    "ALEXIOSI":"BYZANTIUM","JOHNDOUKAS":"BYZANTIUM","JOHNDOUKASW":"BYZANTIUM","ANDRONIKOSDOUKAS":"BYZANTIUM",
    "MARIABULGARIA":"BYZANTIUM","IRENEDOUKAINA":"BYZANTIUM","THEODORAKOMNENE":"BYZANTIUM",
    "CONSTANTINEANGELOS":"BYZANTIUM","ANDRONIKOSANGELOS":"BYZANTIUM","EUPHROSYNEK":"BYZANTIUM",
    "MEROVECH":"CAROLINGIAN","MEROVECHW":"CAROLINGIAN","CHILDERICI":"CAROLINGIAN","BASINA":"CAROLINGIAN",
    "CLOVISI":"CAROLINGIAN","CLOTILDE":"CAROLINGIAN","CHLOTHARI":"CAROLINGIAN","INGUNDFR":"CAROLINGIAN",
    "BLITHILD":"CAROLINGIAN","ANSBERTUS":"CAROLINGIAN","ARNOALD":"CAROLINGIAN","DODA":"CAROLINGIAN",
    # Plantagenet / Angevin / Lancaster / York
    "FULKIV":"PLANTAGENET","BERTRADE":"PLANTAGENET","FULK":"PLANTAGENET","ERM":"PLANTAGENET",
    "GOA":"PLANTAGENET","HII":"PLANTAGENET","EOA":"PLANTAGENET","RICHLION":"PLANTAGENET",
    "BERENG":"PLANTAGENET","KJ":"PLANTAGENET","IOA2":"PLANTAGENET","HIII":"PLANTAGENET",
    "EOP":"PLANTAGENET","EI":"PLANTAGENET","EOC":"PLANTAGENET","EII":"PLANTAGENET","ISAB":"PLANTAGENET",
    "EIII":"PLANTAGENET","PHILH":"PLANTAGENET","BP":"PLANTAGENET","JOANKENT":"PLANTAGENET",
    "RICHARDII":"PLANTAGENET","LIONEL":"PLANTAGENET","JOG":"PLANTAGENET","BLANCHEL":"PLANTAGENET",
    "KATS":"PLANTAGENET","CONSTCAST":"IBERIA","EOL":"PLANTAGENET","RY":"PLANTAGENET","CN":"PLANTAGENET",
    "EIV":"PLANTAGENET","EW":"PLANTAGENET","RICHIII":"PLANTAGENET","ANNENEV":"PLANTAGENET",
    "WARWICK":"PLANTAGENET","ANNEBEAU":"PLANTAGENET","HENRYIV":"PLANTAGENET","HENRYV":"PLANTAGENET",
    "HENRYVI":"PLANTAGENET","MARGANJOU":"FRANCE","CV":"PLANTAGENET","EDWWESTM":"PLANTAGENET",
    "EDV":"PLANTAGENET","RICHSHREWS":"PLANTAGENET","EDWMID":"PLANTAGENET",
    "JOANBEAU":"PLANTAGENET","RALPHNEV":"PLANTAGENET","MBE":"PLANTAGENET","RW":"PLANTAGENET",
    "JL":"PLANTAGENET","MATILDAPLANT_":"NORMANDY",
    "CECILYYORK":"PLANTAGENET","ANNEYORK":"PLANTAGENET","CATHYORK":"PLANTAGENET",
    "BRIDGYORK":"PLANTAGENET","MARYYORK":"PLANTAGENET",
    # Scripture & the Patriarchs — Genesis ascent Adam -> Isaac (Gen 5 & 11)
    "ADAM":"SCRIPTURE","EVE":"SCRIPTURE","SETH":"SCRIPTURE","SETHW":"SCRIPTURE",
    "ENOSH":"SCRIPTURE","ENOSHW":"SCRIPTURE","KENAN":"SCRIPTURE","KENANW":"SCRIPTURE",
    "MAHALALEL":"SCRIPTURE","MAHALALELW":"SCRIPTURE","JARED":"SCRIPTURE","JAREDW":"SCRIPTURE",
    "ENOCH":"SCRIPTURE","ENOCHW":"SCRIPTURE","METHUSELAH":"SCRIPTURE","METHUSELAHW":"SCRIPTURE",
    "LAMECH":"SCRIPTURE","LAMECHW":"SCRIPTURE","NOAH":"SCRIPTURE","NAAMAH":"SCRIPTURE",
    "SHEM":"SCRIPTURE","SHEMW":"SCRIPTURE","ARPHAXAD":"SCRIPTURE","ARPHAXADW":"SCRIPTURE",
    "SHELAH":"SCRIPTURE","SHELAHW":"SCRIPTURE","EBER":"SCRIPTURE","EBERW":"SCRIPTURE",
    "PELEG":"SCRIPTURE","PELEGW":"SCRIPTURE","REU":"SCRIPTURE","REUW":"SCRIPTURE",
    "SERUG":"SCRIPTURE","SERUGW":"SCRIPTURE","NAHOR":"SCRIPTURE","NAHORW":"SCRIPTURE",
    "TERAH":"SCRIPTURE","TERAHW":"SCRIPTURE","ABRAHAM":"SCRIPTURE","SARAH":"SCRIPTURE",
    "ISAAC":"SCRIPTURE","REBEKAH":"SCRIPTURE","JACOBISRAEL":"SCRIPTURE","ESAU":"SCRIPTURE","ESAUW":"SCRIPTURE",
    # Royal / messianic line Judah -> David -> Christ (Ruth 4, 1 Chron, Matthew 1)
    "LEAH":"SCRIPTURE","JUDAH":"SCRIPTURE","TAMAR":"SCRIPTURE","PEREZ":"SCRIPTURE","PEREZW":"SCRIPTURE",
    "HEZRON":"SCRIPTURE","HEZRONW":"SCRIPTURE","RAM":"SCRIPTURE","RAMW":"SCRIPTURE",
    "AMMINADAB":"SCRIPTURE","AMMINADABW":"SCRIPTURE","NAHSHON":"SCRIPTURE","NAHSHONW":"SCRIPTURE",
    "SALMON":"SCRIPTURE","RAHAB":"SCRIPTURE","BOAZ":"SCRIPTURE","RUTH":"SCRIPTURE",
    "OBED":"SCRIPTURE","OBEDW":"SCRIPTURE","JESSE":"SCRIPTURE","JESSEW":"SCRIPTURE",
    "DAVID":"SCRIPTURE","BATHSHEBA":"SCRIPTURE","SOLOMON":"SCRIPTURE","SOLOMONW":"SCRIPTURE",
    "REHOBOAM":"SCRIPTURE","REHOBOAMW":"SCRIPTURE","ABIJAH":"SCRIPTURE","ABIJAHW":"SCRIPTURE",
    "ASA":"SCRIPTURE","ASAW":"SCRIPTURE","JEHOSHAPHAT":"SCRIPTURE","JEHOSHAPHATW":"SCRIPTURE",
    "JORAM":"SCRIPTURE","JORAMW":"SCRIPTURE","UZZIAH":"SCRIPTURE","UZZIAHW":"SCRIPTURE",
    "JOTHAM":"SCRIPTURE","JOTHAMW":"SCRIPTURE","AHAZ":"SCRIPTURE","AHAZW":"SCRIPTURE",
    "HEZEKIAH":"SCRIPTURE","HEZEKIAHW":"SCRIPTURE","MANASSEH":"SCRIPTURE","MANASSEHW":"SCRIPTURE",
    "AMON":"SCRIPTURE","AMONW":"SCRIPTURE","JOSIAH":"SCRIPTURE","JOSIAHW":"SCRIPTURE",
    "JECONIAH":"SCRIPTURE","JECONIAHW":"SCRIPTURE","SHEALTIEL":"SCRIPTURE","SHEALTIELW":"SCRIPTURE",
    "ZERUBBABEL":"SCRIPTURE","ZERUBBABELW":"SCRIPTURE","ABIUD":"SCRIPTURE","ABIUDW":"SCRIPTURE",
    "ELIAKIMB":"SCRIPTURE","ELIAKIMBW":"SCRIPTURE","AZOR":"SCRIPTURE","AZORW":"SCRIPTURE",
    "ZADOKB":"SCRIPTURE","ZADOKBW":"SCRIPTURE","ACHIM":"SCRIPTURE","ACHIMW":"SCRIPTURE",
    "ELIUD":"SCRIPTURE","ELIUDW":"SCRIPTURE","ELEAZARB":"SCRIPTURE","ELEAZARBW":"SCRIPTURE",
    "MATTHAN":"SCRIPTURE","MATTHANW":"SCRIPTURE","JACOBFJOSEPH":"SCRIPTURE","JACOBFJOSEPHW":"SCRIPTURE",
    "JOSEPH":"SCRIPTURE","MARYMOTHER":"SCRIPTURE","JESUS":"SCRIPTURE",
    # Edomite line, Genesis 36 (Esau's wives, sons, grandsons); Antipater/Cypros are the Herodian junction
    "ELIPHAZ":"SCRIPTURE","ELIPHAZW":"SCRIPTURE","REUEL":"SCRIPTURE","REUELW":"SCRIPTURE",
    "JEUSH":"SCRIPTURE","JALAM":"SCRIPTURE","KORAH":"SCRIPTURE",
    "TEMAN":"SCRIPTURE","TEMANW":"SCRIPTURE","OMAR":"SCRIPTURE","ZEPHO":"SCRIPTURE","GATAM":"SCRIPTURE","KENAZE":"SCRIPTURE",
    "TIMNA":"SCRIPTURE","AMALEK":"SCRIPTURE","NAHATH":"SCRIPTURE","ZERAHEDOM":"SCRIPTURE","SHAMMAH":"SCRIPTURE","MIZZAH":"SCRIPTURE",
    "ADAH":"SCRIPTURE","ELON":"SCRIPTURE","ELONW":"SCRIPTURE","BASEMATH":"SCRIPTURE","OHOLIBAMAH":"SCRIPTURE",
    "ANAH":"SCRIPTURE","ANAHW":"SCRIPTURE","ZIBEON":"SCRIPTURE","ZIBEONW":"SCRIPTURE","SEIRHORITE":"SCRIPTURE","SEIRHORITEW":"SCRIPTURE",
    "EDOMDYN":"SCRIPTURE","EDOMDYNW":"SCRIPTURE",
    "ANTIPATER":"ANTIQUITY","CYPROSNAB":"ANTIQUITY","NABATLINE":"SCRIPTURE","NABATLINEW":"SCRIPTURE",
    "ANTIPAS":"ANTIQUITY","ANTIPASW":"ANTIQUITY","ARETAS3":"ANTIQUITY","ARETAS3W":"ANTIQUITY",
    "KEDOM_BELA":"SCRIPTURE","KEDOM_JOBAB":"SCRIPTURE","KEDOM_HUSHAM":"SCRIPTURE","KEDOM_HADAD":"SCRIPTURE",
    "KEDOM_SAMLAH":"SCRIPTURE","KEDOM_SHAUL":"SCRIPTURE","KEDOM_BAALHANAN":"SCRIPTURE","KEDOM_HADAR":"SCRIPTURE",
    # Hasmonean ascent stops at Simeon (1 Macc 2:1)
    "SIMEONMAC":"SCRIPTURE","SIMEONMACW":"SCRIPTURE","YOHANAN":"SCRIPTURE","YOHANANW":"SCRIPTURE",
    # Ishmael, Abraham's firstborn, and the twelve princes (Genesis 16, 25)
    "HAGAR":"SCRIPTURE","ISHMAEL":"SCRIPTURE","ISHMAELW":"SCRIPTURE",
    "NEBAIOTH":"SCRIPTURE","KEDAR":"SCRIPTURE","ADBEEL":"SCRIPTURE","MIBSAM":"SCRIPTURE",
    "MISHMA":"SCRIPTURE","DUMAH":"SCRIPTURE","MASSA":"SCRIPTURE","HADADISH":"SCRIPTURE",
    "TEMA":"SCRIPTURE","JETUR":"SCRIPTURE","NAPHISH":"SCRIPTURE","KEDEMAH":"SCRIPTURE",
    # Noah's other sons + spouse-parents (Terah's house; Bathsheba's father)
    "JAPHETH":"SCRIPTURE","HAM":"SCRIPTURE","TERAHW2":"SCRIPTURE",
    "NAHORBRO":"SCRIPTURE","HARAN":"SCRIPTURE","HARANW":"SCRIPTURE","LOT":"SCRIPTURE",
    "MILCAH":"SCRIPTURE","ISCAH":"SCRIPTURE","BETHUEL":"SCRIPTURE","BETHUELW":"SCRIPTURE",
    "LABAN":"SCRIPTURE","LABANW":"SCRIPTURE","RACHEL":"SCRIPTURE","ELIAM":"SCRIPTURE","ELIAMW":"SCRIPTURE",
    # Jacob's twelve + Dinah + the two servant-mothers
    "REUBEN":"SCRIPTURE","SIMEONJ":"SCRIPTURE","LEVI":"SCRIPTURE","ISSACHAR":"SCRIPTURE","ZEBULUN":"SCRIPTURE",
    "DINAH":"SCRIPTURE","JOSEPHJ":"SCRIPTURE","BENJAMIN":"SCRIPTURE","DAN":"SCRIPTURE","NAPHTALI":"SCRIPTURE",
    "GAD":"SCRIPTURE","ASHER":"SCRIPTURE","BILHAH":"SCRIPTURE","ZILPAH":"SCRIPTURE",
    # David's siblings (1 Chron 2)
    "ELIAB":"SCRIPTURE","ABINADABJ":"SCRIPTURE","SHIMEA":"SCRIPTURE","NETHANELJ":"SCRIPTURE","RADDAI":"SCRIPTURE",
    "OZEM":"SCRIPTURE","JESSE8":"SCRIPTURE","ZERUIAH":"SCRIPTURE","ABIGAILD":"SCRIPTURE",
    # Table of Nations (Gen 10)
    "GOMER":"SCRIPTURE","MAGOG":"SCRIPTURE","MADAI":"SCRIPTURE","JAVAN":"SCRIPTURE","TUBAL":"SCRIPTURE",
    "MESHECH":"SCRIPTURE","TIRAS":"SCRIPTURE","JAPHETHW":"SCRIPTURE","CUSH":"SCRIPTURE","MIZRAIM":"SCRIPTURE",
    "PUT":"SCRIPTURE","CANAAN":"SCRIPTURE","HAMW":"SCRIPTURE","CUSHW":"SCRIPTURE","NIMROD":"SCRIPTURE",
    "ELAM":"SCRIPTURE","ASSHUR":"SCRIPTURE","LUD":"SCRIPTURE","ARAM":"SCRIPTURE",
    # Holy Family / Jesus's kin
    "ANNE":"SCRIPTURE","AARONHOUSE":"SCRIPTURE","AARONHOUSEW":"SCRIPTURE","LEVIHOUSEW":"SCRIPTURE",
    "ELIZABETH":"SCRIPTURE","ZECHARIAH":"SCRIPTURE","JOHNBAPTIST":"SCRIPTURE",
    "EMERENTIA":"SCRIPTURE","EMERENTIAW":"SCRIPTURE","SOBE":"SCRIPTURE","SOBEHUSBAND":"SCRIPTURE",
    "CLOPAS":"SCRIPTURE","MARYCLOPAS":"SCRIPTURE","JAMESJ":"SCRIPTURE","JOSES":"SCRIPTURE",
    "SIMONJ2":"SCRIPTURE","JUDE":"SCRIPTURE",
    # Adam & Eve's other children — Cain, Abel, and Cain's line (Gen 4)
    "CAIN":"SCRIPTURE","ABEL":"SCRIPTURE","AWAN":"SCRIPTURE","AZURA":"SCRIPTURE","OTHERADAM":"SCRIPTURE",
    "EDNA":"SCRIPTURE","BARAKA":"SCRIPTURE","DANEL":"SCRIPTURE","DANELW":"SCRIPTURE",
    "NOAM":"SCRIPTURE","MUALELETH":"SCRIPTURE","DINAHMAH":"SCRIPTURE","EDNAMETH":"SCRIPTURE","BETENOS":"SCRIPTURE",
    "BARAKIL":"SCRIPTURE","BARAKILW":"SCRIPTURE","RASUJAL":"SCRIPTURE","RASUJALW":"SCRIPTURE",
    "AZRIAL":"SCRIPTURE","AZRIALW":"SCRIPTURE","BARAKIEL2":"SCRIPTURE","BARAKIEL2W":"SCRIPTURE",
    "RAKEEL":"SCRIPTURE","RAKEELW":"SCRIPTURE",
    "CAINENOCH":"SCRIPTURE","CAINENOCHW":"SCRIPTURE","IRAD":"SCRIPTURE","IRADW":"SCRIPTURE",
    "MEHUJAEL":"SCRIPTURE","MEHUJAELW":"SCRIPTURE","METHUSHAEL":"SCRIPTURE","METHUSHAELW":"SCRIPTURE",
    "CAINLAMECH":"SCRIPTURE","LAMECHADAH":"SCRIPTURE","ZILLAH":"SCRIPTURE",
    "JABAL":"SCRIPTURE","JUBAL":"SCRIPTURE","TUBALCAIN":"SCRIPTURE","NAAMAHCAIN":"SCRIPTURE",
    # Moses/Aaron/Miriam via Levi; Joseph's sons; Lot's sons; Judah's other sons
    "LEVIWIFE":"SCRIPTURE","KOHATH":"SCRIPTURE","KOHATHW":"SCRIPTURE","AMRAM":"SCRIPTURE","JOCHEBED":"SCRIPTURE",
    "MOSES":"SCRIPTURE","AARON":"SCRIPTURE","MIRIAM":"SCRIPTURE","ZIPPORAH":"SCRIPTURE","GERSHOM":"SCRIPTURE","ELIEZERM":"SCRIPTURE",
    "ELISHEBA":"SCRIPTURE","NADAB":"SCRIPTURE","ABIHU":"SCRIPTURE","ELEAZARA":"SCRIPTURE","ITHAMAR":"SCRIPTURE",
    "ASENATH":"SCRIPTURE","EPHRAIM":"SCRIPTURE","MANASSEHJ":"SCRIPTURE",
    "LOTDAU1":"SCRIPTURE","LOTDAU2":"SCRIPTURE","MOAB":"SCRIPTURE","BENAMMI":"SCRIPTURE",
    "BATHSHUA":"SCRIPTURE","ER":"SCRIPTURE","ONAN":"SCRIPTURE","SHELAHJ":"SCRIPTURE","ZERAHJUDAH":"SCRIPTURE",
    # Apostles by kinship: James the Greater & John (via Salome, Mary's sister)
    "SALOME":"SCRIPTURE","ZEBEDEE":"SCRIPTURE","JAMESGREATER":"SCRIPTURE","JOHNAPOSTLE":"SCRIPTURE",
    # Borgia pope
    "ALEXVI":"MEDICI","VANOZZA":"MEDICI",
}

# --- keyword seeds on the display label (checked after OVERRIDE) ---
KEYWORD = [
    ("MEDICI",["medici","orsini","bardi","tornabuoni","borgia","d'este","auvergne"]),
    ("SCOTLAND",["stewart","bruce","drummond","douglas, earl","of guelders","of denmark","of mar","dunkeld","de ross","ross,","strathearn","atholl","albany","buchan","rothesay","lennox"]),
    ("IBERIA",["castile","aragon","of portugal","of leon","navarre","molina","padilla","enriquez","alburquerque","barcelos","cordoba","of alburquerque","'the wise'","'the avenger'","'the summoned'","'the brave'","'the cruel'","'the saint'","'the conqueror'"]),
    ("HRE",["swabia","saxony","of italy","of metz","of worms","hohenstaufen","barbarossa","stupor mundi","angel","of speyer","of waiblingen","of poitou","altdorf","babenberg","ringelheim","theophanu","of bavaria","of holland","'the wrangler'","salic","carinthia","of sicily","lancia","holland"]),
    ("FRANCE",["of france","of valois","of angouleme","of orleans","of guise","of champagne","of maurienne","of aquitaine","of hainault","of luxembourg","cardinal of lorraine","of bourbon","of anjou","of lorraine","of foix","of brittany","of savoy","de la tour"]),
    ("CAROLINGIAN",["charlemagne","carolingian","of laon","of hesbaye","martel","of herstal","of landen","pepin","altdorf","of flanders","vermandois","'iron arm'","'the bald'","of babenberg"]),
]

# --- id-prefix / regnal seeds ---
def seed(pid, label):
    if pid in OVERRIDE:
        return OVERRIDE[pid]
    if pid.startswith("LK_"):          # Luke's genealogy (David->Nathan->Mary) is all Scripture
        return "SCRIPTURE"
    if pid.startswith("SUM_"):         # the Sumerian King List (a separate Mesopotamian island)
        return "SUMER"
    lab = (label or "").lower()
    # HRE regnal id families
    if pid.endswith("HRE") or pid in ("OTTOI","OTTOII","OTTOIII","OTTOIV","OTTOILLUS","HENRYFOWLER",
        "MATRING","HEDBAB","CONRADII","CONRADIV","CONRADIN","MANFRED","FREDERICKII","FREDIISWAB",
        "FREDISWABIA","FREDIIIHRE","BARBAROSSA","PHILSWAB","MAXIMILIANI","CHARLESV","PHILIPII",
        "PHILIPHANDSOME","JUANAMAD","MARYBURGUNDY","CHARLESBOLD","PHILIPGOOD","ISABBOURBON",
        "GREGORYV","OTTOWORMS","HENRYSPEYER","CONRADRED","LIUTGARDE","ADELAIDEMETZ","GISELASWAB",
        "AGNESPOITOU","BERTHASAVOY","AGNESWAIB","JUDITHBAV","BEATBURG","IRENEANG","ISAACANGELOS",
        "CONSTSICILY","ISABJER","ISABELLAENG","MARGSICILY","BIANCALANCIA","HENRYLION","HENRYBAV",
        "HENRYWRANGLER","CUNIGUNDE","ADELAIDEIT","THEOPHANU","EADGYTH","MATSAX","BALDIII",
        "ISABPORTUGAL3","FREDIII","ELEANORPORT","PHILIPPALANC","JOAOI","DUARTE","PEDROCOIMBRA",
        "HENRYNAV","ISABBURGUNDY","JOHNCONST","FERDINANDHOLY","ISABBARCELOS","LIUTGARDSAX",
        "OTAARNULF","RICHARDIS"):
        return "HRE"
    for dyn, kws in KEYWORD:
        if any(k in lab for k in kws):
            return dyn
    return None

def main():
    d = load_merged()
    people = d["people"]; unions = d["unions"]

    # neighbor structure
    spouses = defaultdict(set)     # person -> co-parents
    children = defaultdict(set)    # person -> their children
    parents = defaultdict(set)     # person -> their parents (from birth union)
    for u in unions.values():
        p = u["parents"]; c = u["children"]
        for a in p:
            for b in p:
                if a != b: spouses[a].add(b)
            for ch in c:
                children[a].add(ch); parents[ch].add(a)

    dyn = {}
    for pid, info in people.items():
        s = seed(pid, info.get("label"))
        if s: dyn[pid] = s

    # propagate: parent -> child -> spouse, to fixpoint.
    # Deterministic: iterate ids sorted and prefer neighbors in a fixed order,
    # so bucket counts don't wobble between builds.
    for _ in range(40):
        changed = False
        for pid in sorted(people):
            if pid in dyn: continue
            cand = None
            for src in sorted(parents[pid]) + sorted(children[pid]) + sorted(spouses[pid]):
                if src in dyn: cand = dyn[src]; break
            if cand:
                dyn[pid] = cand; changed = True
        if not changed: break

    unclassified = [p for p in people if p not in dyn]

    # bridges: unions whose parents differ in dynasty
    bridges = []
    for u in unions.values():
        ps = u["parents"]
        if len(ps) == 2 and ps[0] in dyn and ps[1] in dyn and dyn[ps[0]] != dyn[ps[1]]:
            bridges.append((u["id"], ps[0], dyn[ps[0]], ps[1], dyn[ps[1]]))

    json.dump({"dynasty_of": dyn,
               "dynasties": DYNASTIES,
               "unclassified": unclassified},
              open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)

    counts = Counter(dyn.values())
    print("=== bucket sizes ===")
    for key, title in DYNASTIES:
        print(f"  {key:13s} {counts.get(key,0):3d}  {title}")
    print(f"  {'(unclassified)':13s} {len(unclassified):3d}  {unclassified}")
    print(f"\ntotal classified: {sum(counts.values())} / {len(people)}")
    print(f"bridge unions (cross-page marriages): {len(bridges)}")
    bd = Counter(tuple(sorted((b[2],b[4]))) for b in bridges)
    print("\n=== bridges by dynasty pair ===")
    for pair, n in bd.most_common():
        print(f"  {n:2d}  {pair[0]} <-> {pair[1]}")

if __name__ == "__main__":
    main()
