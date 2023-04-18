# Copyright © 2023 Technology Matters
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published
# by the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program. If not, see https://www.gnu.org/licenses/.

from django.conf import settings
from django.contrib.sitemaps import GenericSitemap
from django.contrib.sites.models import Site

from apps.core.models import Landscape

# Because sitemap crawlers cannot execute JavaScript, the sitemap must be generated by
# the backend and not the web client.
#
# The web client has a sitemap.xml file which is a sitemap index. It contains a single item,
# https://api.terraso.org/sitemap.xml, which is handled by the following path:


class WebClientSitemap(GenericSitemap):
    protocol = settings.WEB_CLIENT_PROTOCOL

    def get_urls(self, site=None, **kwargs):
        site = Site(domain=settings.WEB_CLIENT_DOMAIN)
        return super().get_urls(site=site, **kwargs)

    @classmethod
    def pathargs(cls):
        return {"sitemaps": {"blog": WebClientSitemap(WebClientSitemap.landscapes())}}

    @classmethod
    def landscapes(cls):
        return {"queryset": Landscape.objects.all()}
