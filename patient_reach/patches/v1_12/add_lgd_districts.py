"""Add the districts care's Patient District list lacks, from the Local Government
Directory as of 12-Oct-2026 (Dataful dataset 21838), and put five districts
under their right State (change request of 23-Oct-2026).

District is now mandatory and the popup filters it by State, so a district that
is missing, or filed under another State, cannot be chosen at all. Compared
against care's 835 districts by name within State: districts care already holds
under an older or variant spelling (Anantapur, Allahabad, "Bengaluru (Bangalore)
Urban") are not added a second time. Names that are already taken by a district
in another State get that State's suffix, as "Hamirpur(Hp)" already does.

The five moved districts have no caregivers linked to them. Nothing is renamed
or deleted, and no Patient is changed. Idempotent.
"""

import frappe

NEW = {
	"ANDHRA PRADESH": [
		"Alluri Sitharama Raju", "Anakapalli", "Annamayya", "Bapatla", "Dr. B.R. Ambedkar Konaseema",
		"Eluru", "Kakinada", "Markapuram", "Nandyal", "NTR", "Palnadu", "Parvathipuram Manyam",
		"Polavaram", "Sri Sathya Sai", "Tirupati",
	],
	"ARUNACHAL PRADESH": [
		"Anjaw", "Bichom", "Changlang", "Dibang Valley", "East Kameng", "East Siang", "Kamle",
		"Keyi Panyor", "Kra Daadi", "Kurung Kumey", "Leparada", "Lohit", "Longding", "Lower Siang",
		"Lower Subansiri", "Pakke Kessang", "Papum Pare", "Shi Yomi", "Siang", "Tawang", "Tirap",
		"Upper Siang", "Upper Subansiri", "West Kameng", "West Siang",
	],
	"ASSAM": ["Bajali", "Tamulpur"],
	"CHATTISGARH": [
		"Bijapur (Cgh)", "Gaurela-Pendra-Marwahi", "Khairagarh-Chhuikhadan-Gandai",
		"Manendragarh-Chirmiri-Bharatpur", "Mohla-Manpur-Ambagarh Chouki", "Sakti", "Sarangarh-Bilaigarh",
	],
	"DADRA NAGARHAVEL AND DAMAN DIU": ["Diu"],
	"DELHI": ["Central North", "Old Delhi", "Outer North"],
	"GOA": ["Kushavati"],
	"GUJARAT": ["Vav-Tharad"],
	"HARYANA": ["Hansi"],
	"HIMACHAL PRADESH": ["Lahaul and Spiti"],
	"KARNATAKA": ["Vijayanagara"],
	"LAKSHADWEEP": ["Lakshadweep"],
	"MADHYA PRADESH": ["Maihar", "Mauganj", "Niwari", "Pandhurna"],
	"MAHARASHTRA": ["Chhatrapati Sambhajinagar"],
	"MEGHALAYA": ["Eastern West Khasi Hills"],
	"MIZORAM": ["Hnahthial", "Khawzawl", "Saitual"],
	"NAGALAND": ["Chumoukedima", "Meluri", "Niuland", "Noklak", "Shamator", "Tseminyu"],
	"PUNJAB": ["Malerkotla"],
	"RAJASTHAN": [
		"Balotra", "Beawar", "Deeg", "Didwana-Kuchaman", "Khairthal-Tijara", "Kotputli-Behror",
		"Phalodi", "Salumbar",
	],
	"SIKKIM": ["Pakyong", "Soreng"],
	"TAMIL NADU": ["Chengalpattu", "Kallakurichi", "Mayiladuthurai", "Ranipet", "Tenkasi", "Tirupathur"],
	"UTTAR PRADESH": ["Pratapgarh (Up)", "Sambhal"],
	"UTTARKHAND": ["Pauri Garhwal", "Uttarkashi"],
}

# district: (State it is filed under on care, State it belongs to)
MOVE = {
	"Bijnor": ("UTTARKHAND", "UTTAR PRADESH"),
	"Unakoti": ("UTTARKHAND", "TRIPURA"),
	"Tehri Garhwal": ("GUJARAT", "UTTARKHAND"),
	"Daman": ("GUJARAT", "DADRA NAGARHAVEL AND DAMAN DIU"),
	# HP keeps "Hamirpur(Hp)"; the plain one is UP's.
	"Hamirpur": ("HIMACHAL PRADESH", "UTTAR PRADESH"),
}


def execute():
	added = skipped = moved = 0
	for state, districts in NEW.items():
		if not frappe.db.exists("Patient State", state):
			print(f"[patient_reach v1_12 districts] no Patient State {state}; {len(districts)} skipped")
			skipped += len(districts)
			continue
		for district in districts:
			if frappe.db.exists("Patient District", district):
				continue
			frappe.get_doc({"doctype": "Patient District", "district": district, "state": state}).insert(
				ignore_permissions=True
			)
			added += 1
	for district, (wrong, right) in MOVE.items():
		if frappe.db.get_value("Patient District", district, "state") == wrong and frappe.db.exists(
			"Patient State", right
		):
			frappe.db.set_value("Patient District", district, "state", right)
			moved += 1
	print(f"[patient_reach v1_12 districts] added {added}, moved {moved}, skipped {skipped}")
