import scrapy

from locations.categories import Categories, apply_category
from locations.dict_parser import DictParser
from locations.hours import DAYS_WEEKDAY, OpeningHours

API_BASE = "https://enyakinptt.ptt.gov.tr"

class PttTRSpider(scrapy.Spider):
    name = "ptt_tr"
    item_attributes = {"brand": "PTT", "brand_wikidata": "Q3079259"}
    # id to JSON province
    provinces = {}

    def start_requests(self):
        yield scrapy.Request(f"{API_BASE}/EnYakinPTT/Home/getirTumIller", callback=self.parse_provinces)
    
    def parse_provinces(self, response):
        for item in response.json():
            # item['Kod']: int from 0 to 81 (same as Turkish province plate numbers)
            province_id = str(item['Kod'])
            
            self.provinces[province_id] = {"name": clean_str(item['Ad']), "districts": {}}

            yield scrapy.FormRequest(f"{API_BASE}/EnYakinPTT/Home/getirIlcelerIlIDden", formdata={"ilID": province_id}, meta={"ilID": province_id}, callback=self.parse_districts)

    def parse_districts(self, response):
        for item in response.json():
            province_id = response.meta["ilID"]
            district_id = str(item['Kod'])

            self.provinces[province_id]["districts"][district_id] = {"name": clean_str(item['Ad'])}

            yield scrapy.FormRequest(f"{API_BASE}/EnYakinPTT/Home/getirMahKoyIlceden", formdata={"ilID": province_id, "ilceID": district_id}, meta={"ilID": province_id, "ilceID": district_id}, callback=self.parse_neighborhoods)
    
    def parse_neighborhoods(self, response):
        for item in response.json():
            province_id = response.meta["ilID"]
            district_id = response.meta["ilceID"]
            neighborhood_id = str(item['Kod'])

            yield scrapy.FormRequest("http://localhost:8080/EnYakinPTT/Home/getirIsyerleri", formdata={"ilID": province_id, "ilceID": district_id, "mahKoyID": neighborhood_id}, meta={"ilID": province_id, "ilceID": district_id, "mahKoyID": neighborhood_id}, callback=self.parse)

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
            d["phone"] = item["Telefon"]
            d["state"] = province
            d["city"] = district
            d["opening_hours"] = parse_opening_hours(item)
            
            apply_category(Categories.POST_OFFICE, d)

            return d
        
def parse_opening_hours(item):
    opening_hours = OpeningHours()
    closed = "KAPALI"

    weekday: str = item["HaftaIci"]
    saturday: str = item["Cumartesi"]
    sunday: str = item["Pazar"]

    if weekday != closed:
        parse_hours_str(weekday, opening_hours, DAYS_WEEKDAY)       
    if saturday != closed:
        parse_hours_str(saturday, opening_hours, "Sa")
    if sunday != closed:
        parse_hours_str(sunday, opening_hours, "Su")

    return opening_hours.as_opening_hours()

def parse_hours_str(hour_str: str, oh: OpeningHours, days: str | list[str]):
    days = [days] if isinstance(days, str) else days
    hour_str = hour_str.split("/")
    for hour_range_str in hour_str:
        hour_range_elements = hour_range_str.strip().split("-")
        if len(hour_range_elements) == 2:
            oh.add_days_range(days=days, open_time=hour_range_elements[0], close_time=hour_range_elements[1], time_format="%H:%M")

def clean_str(s: str):
    return ' '.join(s.split())