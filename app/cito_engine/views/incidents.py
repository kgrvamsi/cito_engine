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

from datetime import datetime, timedelta
from django.conf import settings
from django.db.models import Q
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.views.generic.edit import FormView
from django.template import RequestContext
from django.shortcuts import redirect, render_to_response, get_object_or_404
from django.http import Http404, HttpResponse
from django.utils import timezone
from braces.views import LoginRequiredMixin
from cito_engine.models import EventActionLog, Incident, IncidentLog, Team, JIRATickets
from cito_engine.forms import incidents
from comments.models import Comments
from comments.forms import CommentsForm


def get_incident_stats(team_id=None):
    last24hrs = timezone.make_aware(datetime.now() - timedelta(hours=24), timezone.get_current_timezone())
    stats = dict()
    if not team_id:
        stats['active'] = Incident.objects.filter(status__iexact='Active').count()
        stats['acknowledged'] = Incident.objects.filter(status__iexact='Acknowledged').count()
        stats['cleared'] = Incident.objects.filter(status__iexact='Cleared', firstEventTime__gte=last24hrs).count()
    else:
        stats['active'] = Incident.objects.filter(status__iexact='Active', event__team_id=team_id).count()
        stats['acknowledged'] = Incident.objects.filter(status__iexact='Acknowledged', event__team_id=team_id).count()
        stats['cleared'] = Incident.objects.filter(status__iexact='Cleared', firstEventTime__gte=last24hrs,
                                                   event__team_id=team_id).count()
    return stats


def parse_order_by(order_by):
    ordering_list = dict(a_fe='firstEventTime',
                         a_le='lastEventTime',
                         a_count='total_incidents',
                         d_fe='-firstEventTime',
                         d_le='-lastEventTime',
                         d_count='-total_incidents',
                         )

    return ordering_list.get(order_by, None)

@login_required(login_url='/login/')
def view_all_incidents(request, team_id=None, incident_status='active'):
    if request.user.perms.access_level > 4:
        return render_to_response('unauthorized.html', context_instance=RequestContext(request))
    if incident_status not in ['Active', 'active', 'Acknowledged', 'acknowledged', 'Cleared', 'cleared']:
        raise Http404("No such incident")
    query_params = dict()
    render_vars = dict()
    render_vars['page_title'] = 'Viewing %s incidents' % incident_status
    render_vars['incident_status'] = incident_status
    query_params['status__iexact'] = incident_status

    order_by = parse_order_by(request.GET.get('order_by'))

    if not team_id:
        render_vars['stats'] = get_incident_stats()
        render_vars['redirect_to'] = '/incidents/view/%s' % incident_status
    else:
        query_params['event__team_id'] = team_id
        team = get_object_or_404(Team, pk=team_id)
        render_vars['page_title'] += ' for %s' % team.name
        render_vars['stats'] = get_incident_stats(team_id)
        render_vars['redirect_to'] = '/incidents/view/%s/%s' % (team_id, incident_status)
        render_vars['team'] = team

    if order_by:
        incident_list = Incident.objects.filter(**query_params).order_by(order_by)
        render_vars['order_by'] = request.GET.get('order_by')
    else:
        incident_list = Incident.objects.filter(**query_params)
    # TODO: Convert 'Pages per result' into global and user setting
    paginator = Paginator(incident_list, 25)
    try:
        render_vars['incidents'] = paginator.page(request.GET.get('page'))
    except PageNotAnInteger:
        # If page is not an integer, deliver first page.
        render_vars['incidents'] = paginator.page(1)
    except EmptyPage:
        # If page is out of range (e.g. 9999), deliver last page of results.
        render_vars['incidents'] = paginator.page(paginator.num_pages)

    render_vars['box_title'] = render_vars['page_title']
    render_vars['auto_refresh_page'] = True
    # JIRA stuff
    if settings.JIRA_ENABLED:
        render_vars['jira_enabled'] = True
        render_vars['jira_url'] = '%s/browse/' % settings.JIRA_OPTS['URL']
    return render_to_response('view_all_incidents.html', render_vars, context_instance=RequestContext(request))


@login_required(login_url='/login/')
def view_single_incident(request, incident_id):
    if request.user.perms.access_level > 4:
        return render_to_response('unauthorized.html', context_instance=RequestContext(request))
    incident = get_object_or_404(Incident, pk=incident_id)
    if settings.JIRA_ENABLED:
        jira_enabled = True
        jira_url = '%s/browse/' % settings.JIRA_OPTS.get('URL')
        try:
            jira = JIRATickets.objects.get(incident=incident)
        except JIRATickets.DoesNotExist:
            pass
    incidentlogs = IncidentLog.objects.filter(incident=incident).order_by('timestamp')
    eventactionlogs = EventActionLog.objects.filter(incident=incident).order_by('dateAdded')
    comments = Comments.objects.filter(incident=incident).order_by('date_added')
    comments_form = CommentsForm()
    redirect_to = '/incidents/view/%s/' % incident.id
    return render_to_response('view_incident.html', locals(), context_instance=RequestContext(request))


@login_required(login_url='/login/')
def toggle_incident_status(request):
    if request.user.perms.access_level > 4:
        return render_to_response('unauthorized.html', context_instance=RequestContext(request))
    if request.method == "POST":
        form = incidents.IncidentToggleForm(request.POST)
        if form.is_valid():
            incident_id = form.cleaned_data['incident_id']
            form_incident_status = form.cleaned_data['incident_status']
            incident = get_object_or_404(Incident, pk=incident_id)

            # Check if user belongs to incident owning team
            try:
                request.user.team_set.get(pk=incident.event.team.id)
            except Team.DoesNotExist:
                error_msg = "You cannot perform this action because you do not belong to this team."
                return render_to_response('unauthorized.html', {'error_msg': error_msg},
                                          context_instance=RequestContext(request))
            now = timezone.make_aware(datetime.utcnow(), timezone.get_current_timezone())
            incident.toggle_status(form_incident_status, request.user, now)
            incident.save()
            if form.cleaned_data['redirect_to']:
                return redirect(form.cleaned_data['redirect_to'])
            else:
                return redirect('/incidents/view/%s' % incident_id)

        # Send the user back to incidents if form is invalid
        return redirect('/incidents/')


@login_required(login_url='/login/')
def view_element(request):
    render_vars = dict()
    if request.user.perms.access_level > 4:
        return render_to_response('unauthorized.html', context_instance=RequestContext(request))
    if request.method == "POST":
        form = incidents.ElementSearchForm(request.POST)
        if form.is_valid():
            search_term = form.cleaned_data.get('search_term')
            render_vars['search_term'] = search_term
            render_vars['incidents'] = Incident.objects.filter(~Q(status__iexact='Cleared'),
                                                               element__icontains=search_term)
    else:
        form = incidents.ElementSearchForm()
    render_vars['search_form'] = form
    return render_to_response('view_elements.html', render_vars, context_instance=RequestContext(request))


class BulkToggleIncidents(LoginRequiredMixin, FormView):
    template_name = 'generic_form.html'
    form_class = incidents.BulkToggleIncidentForm
    success_url = '/incidents/'

    def get_context_data(self, **kwargs):
        context = super(BulkToggleIncidents, self).get_context_data(**kwargs)
        context['page_title'] = context['box_title'] = 'Bulk toggle incidents'
        return context

    def form_valid(self, form):
        incidents = form.cleaned_data.get('incidents')
        toggle_status = form.cleaned_data.get('toggle_status')
        # make sure we received a list of incident ids
        try:
            incident_list = [int(i) for i in incidents.split(',')]
        except:
            return HttpResponse(status=400, content=b'Bad instance IDs')

        if not incident_list:
            return redirect(self.success_url)

        for incident in Incident.objects.filter(pk__in=incident_list):
            if incident.status != toggle_status:
                incident.toggle_status(status=toggle_status,
                                       user=self.request.user,
                                       time=datetime.utcnow())
                incident.save()

        return redirect(self.success_url)
