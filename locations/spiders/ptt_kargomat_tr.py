import scrapy

from locations.categories import Categories, apply_category
from locations.dict_parser import DictParser

BASE_URL = "https://enyakinptt.ptt.gov.tr"


class PttKargomatTRSpider(scrapy.Spider):
    name = "ptt_kargomat_tr"
    item_attributes = {"brand": "PTT", "brand_wikidata": "Q3079259"}
    # id to JSON province
    provinces = {}

    def start_requests(self):
        yield scrapy.Request(f"{BASE_URL}/EnYakinPTT/Home/getirTumIller", callback=self.parse_provinces)

    def parse_provinces(self, response):
        for item in response.json():
            # item['Kod']: int from 0 to 81 (same as Turkish province plate numbers)
            province_id = str(item["Kod"])

            self.provinces[province_id] = {"name": clean_str(item["Ad"]), "districts": {}}

            yield scrapy.FormRequest(
                f"{BASE_URL}/EnYakinPTT/Home/getirIlcelerIlIDden",
                formdata={"ilID": province_id},
                meta={"ilID": province_id},
                callback=self.parse_districts,
            )

    def parse_districts(self, response):
        for item in response.json():
            province_id = response.meta["ilID"]
            district_id = str(item["Kod"])

            self.provinces[province_id]["districts"][district_id] = {"name": clean_str(item["Ad"])}

            yield scrapy.FormRequest(
                f"{BASE_URL}/EnYakinPTT/Home/getirMahKoyIlceden",
                formdata={"ilID": province_id, "ilceID": district_id},
                meta={"ilID": province_id, "ilceID": district_id},
                callback=self.parse_neighborhoods,
            )

    def parse_neighborhoods(self, response):
        for item in response.json():
            province_id = response.meta["ilID"]
            district_id = response.meta["ilceID"]
            neighborhood_id = str(item["Kod"])

            yield scrapy.FormRequest(
                f"{BASE_URL}/EnYakinPTT/Home/getirKargomat",
                formdata={"ilID": province_id, "ilceID": district_id, "mahKoyID": neighborhood_id},
                meta={"ilID": province_id, "ilceID": district_id, "mahKoyID": neighborhood_id},
                callback=self.parse,
            )

    def parse(self, response):
        for item in response.json():
            province_id = response.meta["ilID"]
            district_id = response.meta["ilceID"]
            _neighborhood_id = response.meta["mahKoyID"]

            province = self.provinces[province_id]["name"]
            district = self.provinces[province_id]["districts"][district_id]["name"]

            d = DictParser.parse(item)
            d["ref"] = item["Sira"]
            d["name"] = clean_str(item["Ad"])
            d["addr_full"] = item["Adres"]
            d["state"] = province
            d["city"] = district

            apply_category(Categories.PARCEL_LOCKER, d)

            return d


def clean_str(s: str):
    return " ".join(s.split())
