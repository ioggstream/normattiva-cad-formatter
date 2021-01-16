import logging
from pathlib import Path

import scrapy
from scrapy import FormRequest
from scrapy.http import Request
import re
import yaml

logging.basicConfig(level=logging.DEBUG)


class BasicSpider(scrapy.Spider):
    name = "basic"
    allowed_domains = ["www.normattiva.it"]
    start_urls = [
        "https://www.normattiva.it/uri-res/"
        "N2Ls?urn:nir:stato:decreto.legislativo:2005-03-07;82!vig=2021-01-16"
    ]

    def parse(self, response):
        cookie = response.headers["Set-Cookie"]
        self.codiceRedazionale = response.selector.xpath(
            '//input[@name="atto.codiceRedazionale"]'
        ).attrib["value"]
        self.dataPubblicazioneGazzetta = response.selector.xpath(
            '//input[@name="atto.dataPubblicazioneGazzetta"]'
        ).attrib["value"]
        self.dataVigenza = re.findall(
            "atto.dataVigenza=(\d+-\d+-\d+)", response.body.decode()
        )[0]
        self.titolo = (
            response.selector.xpath('//meta[@property="eli:title"]/@content')
            .get()
            .strip()
        )
        self.logger.info(
            f"Trovate le seguenti informazioni: {self.codiceRedazionale}, "
            f"{self.dataPubblicazioneGazzetta}, {self.dataVigenza}"
        )
        url_1 = (
            f"https://www.normattiva.it/atto/vediMenuExport?"
            f"atto.dataPubblicazioneGazzetta={self.dataPubblicazioneGazzetta}&"
            f"atto.codiceRedazionale={self.codiceRedazionale}&currentSearch="
        )
        yield Request(url=url_1, headers={"Cookie": cookie}, callback=self.parse_export)

    def parse_export(self, response):
        self.logger.info("Sending form from %s", response.url)
        return FormRequest.from_response(
            response,
            formid="anteprima",
            clickdata={"name": "generaXml"},
            callback=self.save_response,
        )

    def save_response(self, response):
        self.logger.info(
            "Visited %s: %s", response.url, response.headers.get("Content-Type")
        )
        dpath = Path("docs/_rst")
        dpath.mkdir(exist_ok=True)
        Path(dpath / "cad.xml").write_bytes(response.body)
        Path(dpath / f"cad-{self.dataVigenza}.xml").write_bytes(response.body)
        document_settings_yaml = Path(f"docs/document_settings.yml")
        document_settings = yaml.safe_load(
            document_settings_yaml.read_text()
        )
        document_settings["document"].update(
            {
                "name": self.titolo,
                "version": f"v{self.dataVigenza}",
            }
        )
        document_settings_yaml.write_text(
            yaml.safe_dump(document_settings)
        )
