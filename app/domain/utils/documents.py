import os

import xlsxwriter
from django.template.loader import render_to_string
from django.utils import timezone
from django.db.models import Count, Sum
from django.core.files import File

from fulfillment.models import Transportation, Shipment


class ManifestGenerator:
    def __init__(self, transportation=None, transportation_id=None):
        if transportation:
            self.transportation = transportation
            self.transportation_id = self.transportation.id

        elif transportation_id:
            self.transportation = Transportation.objects.filter(
                id=transportation_id
            ).first()
            self.transportation_id = self.transportation and self.transportation.id

    def generate_excell(self):
        now = timezone.now()
        formatted_now = now.strftime("%Y_%m_%d")

        excell_file_name = (
            f"Manifest_{formatted_now}_{str(now.timestamp()).replace('.', '_')}.xlsx"
        )
        workbook = xlsxwriter.Workbook(excell_file_name)
        workbook.formats[0].set_font_size(4)
        worksheet = workbook.add_worksheet()

        shipments = Shipment.objects.annotate(
            total_products_quantity=Sum("package__product__quantity")
        ).filter(box__transportation=self.transportation)
        total_shipments = shipments.count()
        total_weight = self.transportation.boxes.aggregate(
            box_weight=Count("total_weight")
        )["box_weight"]
        total_customs = sum([s.declared_price for s in shipments])

        title_format = workbook.add_format(
            {
                "bold": 1,
                "border": 1,
                "align": "center",
                "valign": "vcenter",
                "fg_color": "black",
                "font_color": "white",
            }
        )
        header_format = workbook.add_format({"bold": 1, "font_size": 8})

        worksheet.merge_range("A1:N1", "Manifest", title_format)

        # Write org port
        worksheet.write(1, 0, "Org port", header_format)
        worksheet.write(2, 0, "Dest port", header_format)
        worksheet.write(1, 1, self.transportation.destination_city.code, header_format)
        worksheet.write(2, 1, self.transportation.source_city.code, header_format)

        # Write total number of shipments, total weight, and total number of master bags
        worksheet.merge_range(
            "J2:N2", f"Total no. of shipments {total_shipments}", header_format
        )
        worksheet.merge_range(
            "J3:N3",
            f"Total no. of master bags {self.transportation.boxes.count()}",
            header_format,
        )
        worksheet.merge_range(
            "J4:N4", f"Total shipments weight {total_weight}", header_format
        )
        worksheet.write(6, 0, "Manifest", header_format)
        worksheet.merge_range(
            "D7:E7", f"Total shipments {total_shipments}", header_format
        )
        worksheet.merge_range("F7:G7", f"Total weight {total_weight}", header_format)
        worksheet.merge_range(
            "H7:J7", f"Total customs {total_customs} USD", header_format
        )

        # worksheet.set_column(3, 3, 25)
        # worksheet.set_column(5, 5, 25)
        # worksheet.set_column(7, 7, 25)
        # worksheet.set_column(11, 11, 25)
        # worksheet.set_column(12, 12, 25)
        # Write table head row
        columns = [
            "No",
            "HAWB",
            "ORG",
            "SENDER",
            "SHPR_REF",
            "DEST",
            "RECEIVER",
            "TYPE",
            "WGHT(KG)",
            "CONTAINS_BATTERY",
            "PCS",
            "DESC",
            "CUST(USD)",
            "HS CODES",
        ]

        col = 0

        for column in columns:
            worksheet.write(7, col, column)
            col += 1

        for i in range(1, 12):
            worksheet.set_column(i, i, 18)

        row = 8
        no = 1
        for shipment in shipments:
            worksheet.write(row, 0, no)
            no += 1

            hs_codes = set()
            for package in shipment.packages.all():
                for product in package.products.all():
                    hs_code = product.category.hs_code
                    if hs_code:
                        hs_codes.add(hs_code)

            products_count = getattr(shipment, "total_products_quantity", 1)
            worksheet.write(row, 1, shipment.number)
            worksheet.write(row, 2, self.transportation.source_city.code),
            worksheet.write(
                row, 3, ", ".join(shipment.packages.values_list("seller", flat=True))
            )
            worksheet.write(row, 4, shipment.number)
            worksheet.write(
                row,
                5,
                self.transportation.destination_city.code,
            )
            worksheet.write(row, 6, shipment.recipient.full_name)
            worksheet.write(row, 7, "PPX")
            worksheet.write(row, 8, shipment.fixed_total_weight)
            worksheet.write(row, 9, "YES" if shipment.contains_batteries else "NO")
            worksheet.write(row, 10, products_count)
            worksheet.write(row, 11, shipment.declared_items_title)
            worksheet.write(row, 12, shipment.declared_price)
            worksheet.write(row, 13, ",".join(hs_codes))
            row += 1

        row += 1
        col = 0

        box_columns = ["no", "BAG_NAME", "HEIGHT", "WIDTH", "LENGTH", "WEIGHT"]
        for column in box_columns:
            worksheet.write(row, col, column)
            col += 1

        row += 1
        no = 1
        for box in self.transportation.boxes.all():
            worksheet.write(row, 0, no)
            no += 1

            worksheet.write(row, 1, box.code)
            worksheet.write(row, 2, box.height)
            worksheet.write(row, 3, box.width)
            worksheet.write(row, 4, box.length)
            worksheet.write(row, 5, box.total_weight)

            row += 1

        workbook.close()

        with open(excell_file_name, "rb") as saved_excell_file:
            django_file = File(saved_excell_file)
            self.transportation.manifest.save(excell_file_name, django_file)
            self.transportation.manifest_last_export_time = timezone.now()
            self.transportation.save()

        try:
            os.remove(excell_file_name)
        except OSError:
            pass

        return self.transportation.manifest
