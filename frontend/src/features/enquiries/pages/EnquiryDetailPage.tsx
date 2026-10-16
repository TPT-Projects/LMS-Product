import { ArrowLeft, MoreHorizontal, Repeat, Trash2, UserRound } from 'lucide-react';
import { useRef, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Link, useNavigate, useParams } from 'react-router-dom';

import {
  Alert,
  Badge,
  Button,
  Card,
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
  EmptyState,
  Skeleton,
  Tabs,
  TabsContent,
  TabsList,
  TabsTrigger,
} from '@/components/ui';
import { getErrorMessage } from '@/lib/api/errors';
import { paths } from '@/routes/paths';

import { useDeleteEnquiry, useEnquiry, useUpdateEnquiry } from '../api';
import { ActivityTimeline } from '../components/ActivityTimeline';
import { AttachmentsPanel } from '../components/AttachmentsPanel';
import { CallsPanel } from '../components/CallsPanel';
import { CustomFieldsCard } from '../components/CustomFieldsCard';
import { DetailsCard, SectionTitle } from '../components/DetailsCard';
import { FollowUpsPanel } from '../components/FollowUpsPanel';
import { FormResponseCard } from '../components/FormResponseCard';
import { NotesPanel } from '../components/NotesPanel';
import { QuickActions } from '../components/QuickActions';
import { StatusMenu } from '../components/StatusMenu';

type Tab = 'timeline' | 'notes' | 'calls' | 'followups' | 'attachments';

export default function EnquiryDetailPage() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const id = Number(useParams().id);
  const enquiry = useEnquiry(id);
  const update = useUpdateEnquiry(id);
  const remove = useDeleteEnquiry();
  const [tab, setTab] = useState<Tab>('timeline');
  const noteRef = useRef<HTMLTextAreaElement>(null);

  if (enquiry.isPending) {
    return (
      <div className="mx-auto max-w-6xl space-y-4">
        <Skeleton className="h-8 w-64" />
        <Skeleton className="h-12 w-full" />
        <div className="grid gap-4 lg:grid-cols-[minmax(0,2fr)_minmax(0,3fr)]">
          <Skeleton className="h-80" />
          <Skeleton className="h-80" />
        </div>
      </div>
    );
  }

  if (enquiry.isError || !enquiry.data) {
    return (
      <EmptyState
        icon={UserRound}
        title={t('enquiry.notFound')}
        description={getErrorMessage(enquiry.error)}
        className="py-24"
        action={
          <Link to={paths.enquiries}>
            <Button variant="secondary">{t('enquiry.back')}</Button>
          </Link>
        }
      />
    );
  }

  const e = enquiry.data;
  const { can_edit: canEdit, can_delete: canDelete } = e.permissions;

  const addNote = () => {
    setTab('notes');
    setTimeout(() => noteRef.current?.focus(), 50);
  };

  return (
    <div className="mx-auto max-w-6xl">
      <div className="mb-4">
        <button
          type="button"
          onClick={() => (window.history.length > 1 ? navigate(-1) : navigate(paths.enquiries))}
          className="inline-flex items-center gap-1.5 text-[13px] text-fg-muted hover:text-fg"
        >
          <ArrowLeft className="size-4" aria-hidden /> {t('enquiry.back')}
        </button>
      </div>

      <header className="mb-4 flex flex-wrap items-start gap-3">
        <div className="min-w-0 flex-1">
          <h1 className="flex flex-wrap items-center gap-2 text-xl font-semibold tracking-tight sm:text-2xl">
            <span className="break-words">{e.name || t('enquiries.noName')}</span>
            {e.is_repeat && (
              <Badge tone="accent">
                <Repeat className="mr-1 size-3" aria-hidden />
                {t('enquiries.repeat')}
              </Badge>
            )}
          </h1>
          <div className="mt-1.5 flex flex-wrap items-center gap-2 text-[13px] text-fg-muted">
            <StatusMenu
              status={e.status}
              disabled={!canEdit || update.isPending}
              onChange={(statusId) => update.mutate({ status_id: statusId })}
            />
            <span>·</span>
            <span>{t(`sources.${e.source}`)}</span>
            {e.campaign_name && (
              <>
                <span>·</span>
                <span className="truncate">{e.campaign_name}</span>
              </>
            )}
          </div>
        </div>
        {canDelete && (
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button variant="ghost" size="icon" aria-label={t('common.actions')}>
                <MoreHorizontal className="size-4" />
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end">
              <DropdownMenuItem
                className="text-danger"
                onSelect={async () => {
                  if (!window.confirm(t('enquiry.confirmDelete'))) return;
                  await remove.mutateAsync(e.id);
                  navigate(paths.enquiries, { replace: true });
                }}
              >
                <Trash2 className="size-4" aria-hidden /> {t('enquiry.delete')}
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
        )}
      </header>

      {(update.isError || remove.isError) && (
        <Alert tone="danger" className="mb-4">
          {getErrorMessage(update.error ?? remove.error)}
        </Alert>
      )}

      <div className="sticky top-14 z-20 -mx-4 mb-4 bg-bg/90 px-4 py-2 backdrop-blur sm:static sm:mx-0 sm:bg-transparent sm:p-0 sm:backdrop-blur-none">
        <QuickActions enquiry={e} canEdit={canEdit} onAddNote={addNote} />
      </div>

      <div className="grid gap-4 lg:grid-cols-[minmax(0,2fr)_minmax(0,3fr)]">
        <div className="space-y-4">
          <DetailsCard key={e.updated_at} enquiry={e} />
          <CustomFieldsCard enquiry={e} />
          <Card>
            <SectionTitle>{t('enquiry.contact')}</SectionTitle>
            <div className="space-y-1 px-4 py-3 text-[13px]">
              <p className="font-medium">{e.contact.name || '—'}</p>
              <p className="text-fg-muted">{e.contact.phone_e164 || e.contact.email || '—'}</p>
              <Link
                to={`${paths.contacts}/${e.contact.id}`}
                className="inline-block pt-1 text-accent hover:underline"
              >
                {t('enquiry.contactEnquiries', { count: e.contact.enquiry_count })}
              </Link>
            </div>
          </Card>
          <FormResponseCard enquiryId={e.id} />
        </div>

        <Card className="min-w-0 self-start">
          <Tabs value={tab} onValueChange={(value) => setTab(value as Tab)}>
            <TabsList className="px-2">
              <TabsTrigger value="timeline">{t('enquiry.tabs.timeline')}</TabsTrigger>
              <TabsTrigger value="notes">{t('enquiry.tabs.notes')}</TabsTrigger>
              <TabsTrigger value="calls">{t('enquiry.tabs.calls')}</TabsTrigger>
              <TabsTrigger value="followups">{t('enquiry.tabs.followups')}</TabsTrigger>
              <TabsTrigger value="attachments">{t('enquiry.tabs.attachments')}</TabsTrigger>
            </TabsList>
            <div className="p-4">
              <TabsContent value="timeline" className="pt-0">
                <ActivityTimeline enquiryId={e.id} />
              </TabsContent>
              <TabsContent value="notes" className="pt-0">
                <NotesPanel ref={noteRef} enquiryId={e.id} canEdit={canEdit} />
              </TabsContent>
              <TabsContent value="calls" className="pt-0">
                <CallsPanel enquiryId={e.id} canEdit={canEdit} />
              </TabsContent>
              <TabsContent value="followups" className="pt-0">
                <FollowUpsPanel enquiryId={e.id} canEdit={canEdit} ownerId={e.primary_owner?.id} />
              </TabsContent>
              <TabsContent value="attachments" className="pt-0">
                <AttachmentsPanel enquiryId={e.id} canEdit={canEdit} />
              </TabsContent>
            </div>
          </Tabs>
        </Card>
      </div>
    </div>
  );
}
