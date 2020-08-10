import io
import os
import operator
import tempfile
from functools import reduce

from django.core.files.storage import default_storage
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db.models.fields.files import FieldFile
from django.test import SimpleTestCase, TestCase
from greenwich import raster
from PIL import Image

from spillway.models import upload_to

from .models import RasterStore


def create_image(multiband=False):
    tmpname = os.path.join(
        upload_to.path, os.path.basename(tempfile.mktemp(prefix="tmin_", suffix=".tif"))
    )
    fp = default_storage.open(tmpname, "w+b")
    shape = (5, 5)
    if multiband:
        shape += (3,)
    b = bytearray(range(reduce(operator.mul, shape)))
    ras = raster.frombytes(bytes(b), shape)
    ras.affine = (-120, 2, 0, 38, 0, -2)
    ras.sref = 4326
    ras.save(fp)
    ras.close()
    fp.seek(0)
    return fp


class RasterTestBase(SimpleTestCase):
    use_multiband = False

    def setUp(self):
        name = self.f.name.replace("%s/" % default_storage.location, "")
        ff = FieldFile(None, RasterStore._meta.get_field("image"), name)
        self.data = {"image": ff}

    @classmethod
    def setUpClass(cls):
        cls.f = create_image(cls.use_multiband)
        super().setUpClass()

    @classmethod
    def tearDownClass(cls):
        cls.f.close()
        super().tearDownClass()

    def _image(self, imgdata):
        return Image.open(io.BytesIO(imgdata))
        # return Image.open(imgdata)


class RasterStoreTestBase(RasterTestBase, TestCase):
    def setUp(self):
        super().setUp()
        self.object = RasterStore.objects.create(image=self.data["image"].name)
        self.qs = RasterStore.objects.all()


class RasterStoreTestCase(RasterStoreTestBase):
    def test_array(self):
        point = self.object.geom.centroid.transform(3310, clone=True)
        self.assertEqual(self.object.array(point).squeeze(), 12)

    def test_save_uploadfile(self):
        upload = SimpleUploadedFile("up.tif", self.object.image.read())
        rstore = RasterStore(image=upload)
        rstore.save()
        self.assertTrue(default_storage.exists(rstore.image))
        self.assertEqual(rstore.image.size, self.f.size)

    def test_linear(self):
        self.assertEqual(list(self.object.linear()), [0.0, 6.0, 12.0, 18.0, 24.0])
        self.assertEqual(
            list(self.object.linear((2, 20))), [2.0, 6.5, 11.0, 15.5, 20.0]
        )

    def test_quantiles(self):
        self.assertEqual(list(self.object.quantiles()), [0.0, 6.0, 12.0, 18.0, 24.0])
