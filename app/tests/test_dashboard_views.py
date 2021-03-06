"""Copyright 2014 Cyrus Dasadia

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.
"""

from django.test import TestCase, Client
from django.contrib.auth.models import User
from appauth.models import Perms
from . import factories


class TestDashboardViews(TestCase):
    def setUp(self):
        self.client = Client()
        self.alpha = factories.TeamFactory.create(name='alpha')
        self.omega = factories.TeamFactory.create(name='omega')
        self.user = User.objects.create_user(username='phil', password='phil',
                                             first_name='phil', last_name='phil',
                                             email='phil@planet.hodor')

    def test_dashboard_without_login(self):
        """
        Testing dashboard view without user
        """
        response = self.client.get('/dashboard/')
        self.assertRedirects(response, '/login/?next=/dashboard/')

    def test_team_dashboard(self):
        """
        Testing if team dashboard has team names in it
        """
        self.client.login(username='phil', password='phil')
        response = self.client.get('/dashboard/')
        self.assertContains(response, 'alpha')
        self.assertContains(response, 'omega')

    def test_individual_team_dashboard(self):
        """
        View per team dashboard
        """
        self.client.login(username='phil', password='phil')
        Perms.objects.create(user=self.user, access_level=4).save()
        response = self.client.get('/incidents/view/%d/active/' % self.alpha.id)
        self.assertEqual(response.status_code, 200)