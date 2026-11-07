"""Patient District names, brought to the current official names in the Local
Government Directory (change request of 07-Nov-2026, item 3: "reload the district
with latest Indianized names available in the gov.in portals").

The list on care holds the old and the new spelling of many districts side by
side (Bellary 5 caregivers, "Ballari (Bellary)" none), because it was loaded from
older lists and then added to (v1_12). This moves each old or variant name onto
the official one:

- if care already has a district for the official name (its own spelling or with
  an alias in brackets, like "Kalaburagi (Gulbarga)"), the old one is MERGED
  into it: `rename_doc(merge=True)`, which moves every link (a caregiver's
  District, any other Link) and removes the old district;
- if not, the old one is RENAMED to the official name (Allahabad -> Prayagraj).

Source: LGD district list, daily snapshot of 07-Nov-2026 from
ramseraph.github.io/opendata/lgd (sha256 8edd1bf9...), 790 districts. Every
target below is an LGD name in the same State; a district never moves State.

What is NOT changed, on purpose:
- A name that differs from LGD only in spelling and is the usual English one
  (Aravalli for LGD's "Arvalli", Cuttack for "Kataka", Bagalkot for "Bagalkote",
  the Tamil Nadu spellings). Adopting LGD's would make the list less
  recognisable to the counselling team.
- Names that cannot be placed without knowing the caregiver: Bardhaman and
  Burdwan (since 2017 two districts, Purba and Paschim Bardhaman) and Midnapore
  (Purba or Paschim Medinipur). The districts that hold caregivers are printed.
- "Kanpur" is taken to be Kanpur Nagar (Kanpur Dehat is a district of its own,
  and already on the list).
- Entries that are not districts (Null, Maharashtra, Malegaon, the Lakshadweep
  islands, Delhi's own names).

Idempotent: a name that is no longer there is skipped. Prints counts and the
district names moved (district names, no caregiver data).
"""

import re

import frappe

# care State -> {old or variant name: the LGD name it becomes}
MAP = {
	"ANDHRA PRADESH": {
		"Anantapur": "Ananthapuramu",
		"Cuddapah": "Y.S.R. Kadapa",
		"YSR": "Y.S.R. Kadapa",
		"Nellore": "Sri Potti Sriramulu Nellore",
		"Vishakapatnam": "Visakhapatnam",
	},
	"ASSAM": {
		"Kamrup Metropolitan": "Kamrup Metro",
		"Karimganj": "Sribhumi",
		"Morigaon": "Marigaon",
		"South Salmara-Mankachar": "South Salmara Mancachar",
	},
	"BIHAR": {
		"East Champaran": "Purbi Champaran",
		"East Champaran (Motihari)": "Purbi Champaran",
		"West Champaran": "Pashchim Champaran",
		"Kaimur": "Kaimur (Bhabua)",
	},
	"CHATTISGARH": {
		"Baloda Bazar": "Balodabazar-Bhatapara",
		"Balrampur": "Balrampur-Ramanujganj",
		"Dantewada (South Bastar)": "Dakshin Bastar Dantewada",
		"Gariaband": "Gariyaband",
		"Jaspur": "Jashpur",
		"Kabirdham": "Kabeerdham",
		"Kabirdham (Kawardha)": "Kabeerdham",
		"Kawardha": "Kabeerdham",
		"Koriya": "Korea",
		"Kanker": "Uttar Bastar Kanker",
		"Kanker (North Bastar)": "Uttar Bastar Kanker",
	},
	"GUJARAT": {"Baroda": "Vadodara"},
	"HARYANA": {
		"Gurgaon": "Gurugram",
		"Mewat": "Nuh",
		"Hissar": "Hisar",
		"Sonepat": "Sonipat",
	},
	"JHARKHAND": {"Hazaribag": "Hazaribagh", "Palamau": "Palamu"},
	"KARNATAKA": {
		"Belgaum": "Belagavi",
		"Bellary": "Ballari",
		"Bijapur": "Vijayapura",
		"Gulbarga": "Kalaburagi",
		"Mysore": "Mysuru",
		"Shimoga": "Shivamogga",
		"Tumkur": "Tumakuru",
		"Chickmagalur": "Chikkamagaluru",
		"Chikballapur": "Chikkaballapura",
		"Chikkaballapur": "Chikkaballapura",
		"Chamrajnagar": "Chamarajanagar",
		"Davangere": "Davanagere",
		# Ramanagara district was renamed Bengaluru South (2025).
		"Ramanagar": "Bengaluru South",
		"Ramanagaram": "Bengaluru South",
		"Ramanagara": "Bengaluru South",
	},
	"KERALA": {"Kasargod": "Kasaragod"},
	"MADHYA PRADESH": {
		"Hoshangabad": "Narmadapuram",
		"Narsinghpur": "Narsimhapur",
		"East Nimar": "Khandwa (East Nimar)",
		"Khandwa": "Khandwa (East Nimar)",
		"West Nimar": "Khargone (West Nimar)",
		"Khargone": "Khargone (West Nimar)",
	},
	"MAHARASHTRA": {
		"Ahmed Nagar": "Ahilyanagar",
		"Ahmednagar": "Ahilyanagar",
		"Osmanabad": "Dharashiv",
		"Bid": "Beed",
		"Gondiya": "Gondia",
		"Mumbai City": "Mumbai",
		"Raigarh(Mh)": "Raigad",
	},
	"MIZORAM": {"Saiha": "Siaha"},
	"ODISHA": {
		"Khorda": "Khordha",
		"Jajapur": "Jajpur",
		"Nabarangapur": "Nabarangpur",
		"Sonapur": "Subarnapur",
		"Sonepur": "Subarnapur",
	},
	"PONDICHERRY": {"Pondicherry": "Puducherry"},
	"PUNJAB": {
		"Firozpur": "Ferozepur",
		"Muktsar": "Sri Muktsar Sahib",
		"Nawan Shehar": "Shahid Bhagat Singh Nagar",
		"Nawanshahr": "Shahid Bhagat Singh Nagar",
		"Nawanshahr (Shahid Bhagat Singh Nagar)": "Shahid Bhagat Singh Nagar",
		"Ropar": "Rupnagar",
		"Tarantaran": "Tarn Taran",
	},
	"RAJASTHAN": {
		"Jalor": "Jalore",
		"Jhujhunu": "Jhunjhunu",
		"Jhunjhunun": "Jhunjhunu",
		"Sri Ganganagar": "Ganganagar",
	},
	"SIKKIM": {
		"East Sikkim": "Gangtok",
		"North Sikkim": "Mangan",
		"South Sikkim": "Namchi",
		"West Sikkim": "Gyalshing",
	},
	"TELANGANA": {
		"Bhadrari Kothagudem": "Bhadradri Kothagudem",
		"Kothagudem": "Bhadradri Kothagudem",
		"Kothagudem Colls": "Bhadradri Kothagudem",
		"Gadwal": "Jogulamba Gadwal",
		"Jogulamba": "Jogulamba Gadwal",
		"K.V.Rangareddy": "Ranga Reddy",
		"Mahabuababad": "Mahabubabad",
		"Mahbubnagar": "Mahabubnagar",
		"Mehbubnagar": "Mahabubnagar",
		"Medchal": "Medchal Malkajgiri",
		"Sircilla": "Rajanna Sircilla",
		"Yadadri": "Yadadri Bhuvanagiri",
		"Bhongir": "Yadadri Bhuvanagiri",
	},
	"UTTAR PRADESH": {
		"Allahabad": "Prayagraj",
		"Faizabad": "Ayodhya",
		"Rai Bareli": "Rae Bareli",
		"Sant Ravi Das Nagar": "Bhadohi",
		"Sant Ravidas Nagar Bhadohi": "Bhadohi",
		"Kanshiram Nagar": "Kasganj",
		"Jyotiba Phule Nagar": "Amroha",
		"Prabudh Nagar": "Shamli",
		"Chhatrapati Shahuji Maharaj Ngr": "Amethi",
		"Barlampur": "Balrampur",
		"Kanpur": "Kanpur Nagar",
		"Noida": "Gautam Buddha Nagar",
		"Greater Noida": "Gautam Buddha Nagar",
	},
	"WEST BENGAL": {
		"Haora": "Howrah",
		"Jhargam": "Jhargram",
		"Darjiling": "Darjeeling",
		"East Midnapore": "Purba Medinipur",
		"West Midnapore": "Paschim Medinipur",
		"Puruliya": "Purulia",
		"North Dinajpur": "Uttar Dinajpur",
		"South Dinajpur": "Dakshin Dinajpur",
	},
}

DOCTYPE = "Patient District"


def _key(name):
	return re.sub(r"[^a-z0-9]", "", name.lower())


def _without_alias(name):
	return re.sub(r"\s*\(.*?\)\s*", "", name).strip()


def resolve_target(existing, official):
	"""The name to move an old district to: the one already on the list for
	`official` (spelled the same, or with an alias in brackets), else `official`.
	`existing` is the State's district names."""
	for name in sorted(existing):
		if _key(name) == _key(official) or _key(_without_alias(name)) == _key(official):
			return name
	return official


def execute():
	renamed = merged = 0
	for state, names in MAP.items():
		existing = set(frappe.get_all(DOCTYPE, filters={"state": state}, pluck="name"))
		for old, official in names.items():
			if old not in existing:
				continue
			target = resolve_target(existing - {old}, official)
			if target == old:
				continue
			in_use = frappe.db.count("Patient", {"custom_district": old})
			if target in existing:
				frappe.rename_doc(DOCTYPE, old, target, merge=True, force=True, rebuild_search=False, show_alert=False)
				merged += 1
				print(f"districts: {state}: '{old}' merged into '{target}' ({in_use} caregiver(s) moved)")
			else:
				frappe.rename_doc(DOCTYPE, old, target, force=True, rebuild_search=False, show_alert=False)
				renamed += 1
				existing.add(target)
				print(f"districts: {state}: '{old}' renamed '{target}' ({in_use} caregiver(s) follow it)")
			existing.discard(old)
	left = frappe.db.sql(
		"""select d.state, d.name, count(p.name) from `tabPatient District` d
		left join `tabPatient` p on p.custom_district = d.name
		where d.name in ('Bardhaman', 'Burdwan', 'Midnapore') group by d.state, d.name""",
	)
	for state, name, n in left:
		print(f"districts: LEFT for review: {state}: '{name}' holds {n} caregiver(s); Purba or Paschim needs the caregiver's address")
	print(f"districts: {renamed} renamed, {merged} merged; {frappe.db.count(DOCTYPE)} districts now")
