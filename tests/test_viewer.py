import queue
import unittest
from io import BytesIO
from types import SimpleNamespace
from unittest.mock import Mock, patch

from PIL import Image
from booruget.models import Post
from booruget.viewer import ImageViewer, fetch_image, MAX_IMAGE_BYTES


def post():
    return Post('paheal', '1', '', 'https://example.org/original', 'png',
                640, 480, 'explicit', 'landscape', 'https://example.org/thumb')


def response(data):
    result = Mock()
    result.__enter__ = Mock(return_value=result)
    result.__exit__ = Mock(return_value=False)
    result.iter_content.return_value = iter([data])
    return result


class ViewerTests(unittest.TestCase):
    def test_original_image_and_thumbnail_fallback(self):
        buffer = BytesIO()
        Image.new('RGB', (640, 480)).save(buffer, 'PNG')
        with patch('booruget.viewer.requests.get', return_value=response(buffer.getvalue())) as get:
            image, fallback = fetch_image(post())
            self.assertEqual(image.size, (640, 480))
            self.assertFalse(fallback)
            self.assertEqual(get.call_args.args[0], post().file_url)
        with patch('booruget.viewer.requests.get', side_effect=[response(b'video'), response(buffer.getvalue())]):
            image, fallback = fetch_image(post())
            self.assertTrue(fallback)
            self.assertEqual(image.size, (640, 480))

    def test_stream_limit_rejects_large_downloads(self):
        with patch('booruget.viewer.requests.get', side_effect=lambda *a, **kw: response(b'x'*20)), \
             patch('booruget.viewer.MAX_IMAGE_BYTES', 10):
            with self.assertRaises(ValueError):
                fetch_image(post())

    def test_navigation_preserves_list_order_and_stops_at_ends(self):
        viewer = SimpleNamespace(get_entries=lambda: {'third': post(), 'first': post()},
                                 entry='third', select_entry=Mock(), show=Mock())
        ImageViewer.move(viewer, -1)
        viewer.show.assert_not_called()
        ImageViewer.move(viewer, 1)
        viewer.select_entry.assert_called_once_with('first')
        viewer.show.assert_called_once_with('first')
        viewer.entry = 'first'
        viewer.show.reset_mock()
        ImageViewer.move(viewer, 1)
        viewer.show.assert_not_called()

    def test_late_image_from_previous_selection_is_ignored(self):
        pending = queue.Queue()
        pending.put((1, Image.new('RGB', (10, 10)), False))
        viewer = SimpleNamespace(pending=pending, token=2, image=None,
                                 _controls_if_changed=Mock(), after=Mock(), _poll=Mock())
        ImageViewer._poll(viewer)
        self.assertIsNone(viewer.image)
