import io
import os
import tempfile

from django.core.files.storage import default_storage
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db.models.fields.files import FieldFile
from django.test import SimpleTestCase, TestCase
from greenwich import raster
from PIL import Image

from .models import RasterStore

def create_image():
    tmpname = os.path.basename(tempfile.mktemp(suffix='.tif'))
    fp = default_storage.open(tmpname, 'w+b')
    ras = raster.frombytes(bytes(bytearray(range(25))), (5, 5))
    ras.affine = (-120, 2, 0, 38, 0, -2)
    ras.sref = 4326
    ras.save(fp)
    ras.close()
    fp.seek(0)
    return fp


class RasterTestBase(SimpleTestCase):
    def setUp(self):
        self.f = create_image()
        ff = FieldFile(None, RasterStore._meta.get_field('image'),
                       os.path.basename(self.f.name))
        self.data = {'image': ff}

    def tearDown(self):
        self.f.close()

    def _image(self, imgdata):
        return Image.open(io.BytesIO(imgdata))
        #return Image.open(imgdata)


class RasterStoreTestBase(RasterTestBase, TestCase):
    def setUp(self):
        super(RasterStoreTestBase, self).setUp()
        self.object = RasterStore.objects.create(
            image=os.path.basename(self.f.name))
        self.qs = RasterStore.objects.all()


class RasterStoreTestCase(RasterStoreTestBase):
    def test_save_uploadfile(self):
        upload = SimpleUploadedFile('up.tif', self.object.image.read())
        rstore = RasterStore(image=upload)
        rstore.save()
        self.assertTrue(default_storage.exists(rstore.image))
        self.assertEqual(rstore.image.size, self.f.size)

    def test_linear(self):
        self.assertEqual(list(self.object.linear()),
                         [0., 6., 12., 18., 24.])
        self.assertEqual(list(self.object.linear((2, 20))),
                         [2., 6.5, 11., 15.5, 20.])

    def test_quantiles(self):
        self.assertEqual(list(self.object.quantiles()),
                         [0., 6., 12., 18., 24.])
