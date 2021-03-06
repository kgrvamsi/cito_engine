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

from django import forms
from django.contrib.auth.models import User
from cito_engine.models import Team


class TeamForm(forms.ModelForm):
    class Meta:
        model = Team
        fields = '__all__'

    def __init__(self, *args, **kwargs):
        super(TeamForm, self).__init__(*args, **kwargs)
        self.fields['members'].widget = forms.widgets.CheckboxSelectMultiple()
        self.fields['members'].help_text = "Team members"
        self.fields['members'].queryset = User.objects.filter(is_active=True)