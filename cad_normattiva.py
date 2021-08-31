import logging
import re
from pathlib import Path

import pytest
from scrapy import Selector

log = logging.getLogger()
logging.basicConfig(level=logging.DEBUG)

BASEDIR = "docs/_rst"


INDEX_HEADER = """
Codice dell'amministrazione digitale
####################################

Decreto Legislativo 7 marzo 2005, n. 82
#######################################

.. toctree::

"""


def fix_accent(l):
    """
    Sostituisce apostrofo con l'accento in parole che finiscono per vocale.
    Es: liberta' -> libertà
    Po', po', è vengono ripristinati nella versione corretta
    """
    l = l.replace("a'", "à").replace("e'", "é").replace("i'", "ì").replace("A'", "À")
    l = l.replace("o'", "ò").replace("u'", "ù").replace("E'", "È")
    l = (
        l.replace("pò", "po'")
        .replace("Pò", "Po'")
        .replace(" é ", " è ")
        .replace("e\\'", "è")
        .replace("cioé", "cioè")
    )
    if l[-2:] == " é":
        l = l[:-1] + "è"
    if l[0:2] == "é ":
        l = "è" + l[1:]

    return l


def parse_articolo(a):
    """
    <articolo id="19">
        <num>Art. 19.</num>
        <comma id="art19-com1">
        <num>1</num>
        <corpo>
            <h:p h:style="text-align: center;">Art. 20 </h:p>
            <h:p h:style="text-align: center;">Validita' ed efficacia probatoria dei documenti informatici </h:p>
            <h:br/>
            <h:p h:style="text-align: center;">((ARTICOLO ABROGATO DAL D.LGS. 26 AGOSTO 2016, N. 179)) </h:p>
        </corpo>
        </comma>
    </articolo>
    """
    re_dashes = re.compile("^---+\s*$")
    re_comma = re.compile(r"^([0-9a-z\-]+)\)\s*")
    re_punto = re.compile(r"^([0-9a-z\-]+)\.\s*")

    lines = a.xpath(".//corpo/p/text()")
    lines = [x.extract() for x in lines]

    # Ignore lines made of dashes
    lines = [re_dashes.sub("\n", l) for l in lines]


    # Insert \n at the end of a numbered list.
    j = 1
    while j < len(lines):
        l0, l1 = lines[j-1:j+1]
        #if l1.startswith('(21)'): import pdb; pdb.set_trace()
        l0_numbered = re_comma.match(l0) or re_punto.match(l0)
        l1_numbered = re_comma.match(l1) or re_punto.match(l1)
        if l0_numbered and not l1_numbered:
            lines.insert(j, "\n")
            j += 1
        j += 1

    # Lines matching 'something) .*' are commas or points,
    #  so make them as numbered lists.
    lines = [re_comma.sub(r"\n  \1\) ", l) for l in lines]
    lines = [re_punto.sub(r"\n  \1\. ", l) for l in lines]


    for i, l in enumerate(lines):
        if l.startswith("Art"):
            break
    intro = lines[:i]
    art, headline, *body = lines[i:]
    art = re.sub(r"\.$", "", art)
    title = art + " " + headline
    txt_lines = [title, "^" * len(title), ""] + body + ["\n"]
    txt_intro = fix_accent("\n\n".join(intro + ["\n"])) if i else None
    txt_lines = fix_accent("\n".join(txt_lines))

    if not txt_intro:
        txt_lines = txt_lines.splitlines()
        title, body = '\n'.join(txt_lines[:2]), '\n'.join(txt_lines[2:])

        # Add footnotes: this is a kludge to allow linking each "comma".
        # body, count = re.subn('\. ([A-Z])', r'. [*]_ \1', body)
        # body +=  '\n\n'  + '\n\n'.join(('.. [*] foo' for x in range(count))) + "\n\n"

        txt_lines = title + '\n' + body
    return txt_intro, txt_lines


def mkfilename(capo_id, sezione_id=None, art_id=None):
    return (
        "-".join(
            x
            for x in (
                f"capo_{capo_id}",
                f"sezione_{sezione_id}" if sezione_id else "",
                f"articolo_{art_id}" if art_id is not None else None,
            )
            if x
        )
        + ".rst"
    )


def get_capo_titolo(text):
    if "Sezione" in text:
        capo_titolo, *_ = re.findall("(Capo .*)(Sezione.*)", text, re.I)[0]
        return capo_titolo

    return re.findall("(capo .*)", text, re.I)[0]


class CAD(object):
    def __init__(self, text):
        self.cad = Selector(text=text)
        self.capi = {}
        self.sezioni = []

    def parse(self):
        for s in self.cad.xpath("//capo"):
            sezione, text = parse_capo(s)
            if text.startswith("Capo"):
                capo = re.findall("Capo ([A-Z0-9]+)", text)[0]
                capo_titolo = get_capo_titolo(text)
                self.capi[capo] = {"titolo": capo_titolo, "sezioni": []}

            sezione = re.findall("Sezione ([A-Z0-9]+)", text)
            sezione = "" if not sezione else sezione[0]
            sezione_titolo = re.findall("(Sezione .*)", text)
            print(capo, sezione, f"[{text}]")
            sezione_o = {
                sezione: fix_accent(sezione_titolo[0] if sezione_titolo else ""),
                "articoli": [],
                "intro": "",
            }
            for a in s.xpath(".//articolo"):
                intro_txt, articolo_txt = parse_articolo(a)
                sezione_o["articoli"].append(articolo_txt)
                if intro_txt:
                    sezione_o["intro"] = intro_txt
            self.capi[capo]["sezioni"].append(sezione_o)

    def dump_index(self, outdir=BASEDIR):
        dpath = Path(outdir)

        idx = dpath / ".." / "index.rst"

        with idx.open("w") as fh:
            fh.write(INDEX_HEADER)
            for capo in self.capi:
                fh.write(f"   _rst/capo_{capo}.rst\n")

        for capo_id, capo in self.capi.items():
            capo_fpath = dpath / f"capo_{capo_id}.rst"
            capo_titolo = fix_accent(capo["titolo"])
            capo_txt = [
                f"{capo_titolo}",
                "=" * (len(capo_titolo) + 2),
                "\n.. toctree::\n",
            ]

            for sezione in capo["sezioni"]:
                sezione_id = next(iter(sezione.keys()))
                sezione_titolo = sezione[sezione_id]
                sezione_intro = sezione.get("intro", "")
                if sezione_id:
                    sezione_fpath = dpath / mkfilename(capo_id, sezione_id)
                    capo_txt += [f"   {str(sezione_fpath).replace(f'{outdir}/','')}"]
                    sezione_txt = [
                        sezione_titolo,
                        "-" * (len(sezione_titolo) + 2),
                        "",
                        sezione_intro,
                        "" "\n.. toctree::\n",
                    ]
                    art_dest = sezione_txt
                else:
                    sezione_txt = []
                    art_dest = capo_txt
                for articolo in sezione["articoli"]:
                    art = re.findall("Art[^ ]* ([0-9a-zA-Z\-]+)", articolo)[0]
                    fpath = mkfilename(capo_id, sezione_id, art)
                    article_fpath = dpath / fpath
                    article_fpath.write_text(articolo)
                    art_dest += [f"   {str(article_fpath).replace(f'{outdir}/', '')}"]

                if sezione_txt:
                    sezione_fpath.write_text("\n".join(sezione_txt + ["", ""]))
            capo_fpath.write_text("\n".join(capo_txt + ["", ""]))


def parse_capo(e):
    text = "".join(e.xpath("node()/text()").extract()).strip().strip(" -").strip("(")
    sezione = e.xpath("@id").extract()[0]
    sezione = re.sub("[\r\n]", " ", sezione)
    text = re.sub("[\r\n]", " ", text)
    try:
        capo, testo = re.findall("(Capo [^ ]+) \(*([^)]+)\)*$", text, re.I)[0]
        text = f"{capo}. {testo}"
    except (IndexError, ValueError):
        pass

    return sezione, fix_accent(text)


if __name__ == '__main__':
    cad = Path(f"{BASEDIR}/cad.xml").read_text()
    cadparser = CAD(text=cad)
    cadparser.parse()
    cadparser.dump_index()


@pytest.fixture
def cad():
    return Path("cad.xml").read_text()


def test_cad(cad):
    cadparser = CAD(text=cad)
    cadparser.parse()
    cadparser.dump_index()


def test_capo(cad):
    selector = Selector(text=cad)
    for s in selector.xpath("//capo"):
        id_, text = parse_capo(s)
        assert "Capo I" in text
        assert "1" == id_
        break
