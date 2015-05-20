import io
import os
import tempfile

from django.core.files.storage import default_storage
from django.core.files import File
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import SimpleTestCase, TestCase
from greenwich.raster import frombytes
from PIL import Image

from .models import RasterStore

def create_image():
    tmpname = os.path.basename(tempfile.mktemp(suffix='.tif'))
    fp = default_storage.open(tmpname, 'w+b')
    ras = frombytes(bytes(bytearray(range(25))), (5, 5))
    ras.affine = (-120, 2, 0, 38, 0, -2)
    ras.sref = 4326
    ras.save(fp)
    ras.close()
    fp.seek(0)
    return fp


class RasterTestBase(SimpleTestCase):
    def setUp(self):
        self.f = create_image()
        self.data = {'path': self.f.name, 'file': self.f.name}

    def tearDown(self):
        self.f.close()

    def _image(self, imgdata):
        return Image.open(io.BytesIO(imgdata))


class RasterStoreTestBase(RasterTestBase, TestCase):
    def setUp(self):
        super(RasterStoreTestBase, self).setUp()
        self.object = RasterStore.objects.create(image=File(self.f))
        self.qs = RasterStore.objects.all()


class RasterStoreTestCase(RasterStoreTestBase):
    def test_save_uploadfile(self):
        upload = SimpleUploadedFile('up.tif', self.object.image.read())
        rstore = RasterStore(image=upload)
        rstore.save()
        self.assertTrue(default_storage.exists(rstore.image))
        self.assertEqual(rstore.image.size, self.f.size)
