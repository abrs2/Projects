from xml.dom import ValidationErr
from odoo import fields,models,api
import pdf2image
from pdf2image import convert_from_bytes
from pdf2image.exceptions import (
    PDFInfoNotInstalledError,
    PDFPageCountError,
    PDFSyntaxError
)
from xlrd import open_workbook
import base64
from io import StringIO

class PaoDigitalCatalogPdf(models.Model):
    _name = "pao.digital.catalog.pdf"
    _description = "Pao Digital Catalog PDF"

    name = fields.Char("Nombre de Catalogo",required=True)
    catalog = fields.Binary("Catálogo en formato PDF", required=True)
    images = fields.Binary("Imagenes en formato PNG", compute="import_data_form_file" ,readonly=True)

    @api.depends("catalog")
    def import_data_form_file(self):
        try:
            inputx = StringIO()
            inputx.write(base64.decodebytes(self.catalog))
            book = open_workbook(file_contents=inputx.getvalue())
            self.images = convert_from_bytes(book)
        except TypeError as e:
            raise ValidationErr(u'ERROR: {}'.format(e))

    



    