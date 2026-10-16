import { useTranslation } from 'react-i18next';

import { Alert, Skeleton } from '@/components/ui';
import { getErrorMessage } from '@/lib/api/errors';

import { useMetaStatus } from '../api';
import { ConnectGuide } from '../components/ConnectGuide';
import { ConnectionCard } from '../components/ConnectionCard';
import { ConversionsCard } from '../components/ConversionsCard';
import { FormsCard } from '../components/FormsCard';
import { SyncCard } from '../components/SyncCard';
import { SyncingNotice } from '../components/SyncingNotice';

/** Settings > Integrations > Meta (spec flow F5). */
export default function MetaSettingsPage() {
  const { t } = useTranslation();
  const status = useMetaStatus();

  if (status.isPending) return <Skeleton className="h-48 w-full" />;
  if (status.isError || !status.data) {
    return <Alert tone="danger">{getErrorMessage(status.error) || t('errors.unknown')}</Alert>;
  }
  const connected = status.data.status === 'connected';
  return (
    <div className="space-y-5">
      <SyncingNotice />
      <ConnectionCard status={status.data} />
      <ConnectGuide defaultOpen={!connected} />
      {connected && <FormsCard />}
      {connected && <ConversionsCard />}
      {(connected || status.data.status === 'disconnected') && <SyncCard />}
    </div>
  );
}
