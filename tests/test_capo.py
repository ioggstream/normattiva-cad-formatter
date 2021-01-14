from pathlib import Path
import pytest
from scrapy import Selector
import logging

log = logging.getLogger()
logging.basicConfig(level=logging.DEBUG)


@pytest.fixture
def cad():
    return Path("cad.xml").read_text()


INDEX_HEADER = """
Codice dell'amministrazione digitale
####################################

Decreto Legislativo 7 marzo 2005, n. 82
#######################################

.. toctree::

"""


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
    lines = a.xpath(".//corpo/p/text()")
    title, *body = [x.extract() for x in lines]
    txt_lines = [title, "^" * len(title), ""] + body + ["\n"]
    return "\n".join(txt_lines)


import re


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
                self.capi[capo] = {"titolo": text, "sezioni": []}
            sezione = re.findall("Sezione ([A-Z0-9]+)", text)
            sezione = "" if not sezione else sezione[0]
            sezione_titolo = re.findall("(Sezione .*)", text)
            print(capo, sezione, f"[{text}]")
            sezione_o = {
                sezione: sezione_titolo[0] if sezione_titolo else "",
                "articoli": [],
            }
            for a in s.xpath(".//articolo"):
                txt = parse_articolo(a)
                sezione_o["articoli"].append(txt)

            self.capi[capo]["sezioni"].append(sezione_o)

    def dump_index(self):
        idx = Path("index.rst")

        with idx.open("w") as fh:
            fh.write(INDEX_HEADER)
            for capo in self.capi:
                fh.write(f"   dist/capo_{capo}.rst\n")

        dpath = Path("dist")
        for capo_id, capo in self.capi.items():
            capo_fpath = dpath / f"capo_{capo_id}.rst"
            capo_titolo = capo["titolo"]
            capo_txt = [f"{capo_titolo}", "=" * len(capo_titolo), "\n.. toctree::\n"]

            for sezione in capo["sezioni"]:
                sezione_id = next(iter(sezione.keys()))
                sezione_titolo = sezione[sezione_id]

                if sezione_id:
                    sezione_fpath = dpath / mkfilename(capo_id, sezione_id)
                    capo_txt += [f"   {str(sezione_fpath).replace('dist/','')}"]
                    sezione_txt = [
                        sezione_titolo,
                        "-" * len(sezione_titolo),
                        "\n.. toctree::\n",
                    ]
                    art_dest = sezione_txt
                else:
                    sezione_txt = []
                    art_dest = capo_txt
                for articolo in sezione["articoli"]:
                    art = re.findall("Art.* ([0-9a-zA-Z\-]+)", articolo)[0]
                    fpath = mkfilename(capo_id, sezione_id, art)
                    article_fpath = dpath / fpath
                    article_fpath.write_text(articolo)
                    art_dest += [f"   {str(article_fpath).replace('dist/', '')}"]

                if sezione_txt:
                    sezione_fpath.write_text("\n".join(sezione_txt + ["", ""]))
            capo_fpath.write_text("\n".join(capo_txt + ["", ""]))


def parse_capo(e):
    text = "".join(e.xpath("node()/text()").extract()).strip().strip(" -").strip("(")
    sezione = e.xpath("@id").extract()[0]
    return sezione, text


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
