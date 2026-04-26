import React, { useEffect, useMemo, useRef, useState } from 'react';
import styled from 'styled-components';
import {
  ResponsiveContainer,
  PieChart,
  Pie,
  Cell,
  LineChart,
  Line,
  CartesianGrid,
  XAxis,
  YAxis,
  Tooltip,
  BarChart,
  Bar,
} from 'recharts';
import { useNavigate } from 'react-router-dom';
import { getGmailLeads } from '../api/client';
import { useModalManager } from '../context/ModalManagerContext';
import { useAuth } from '../context/AuthContext';

const Title = styled.h4`
  margin: 0;
  font-size: 1.1rem;
`;
const Card = styled.section`
  background: ${({ theme }) => theme.colors.cardBackground};
  border: 1px solid ${({ theme }) => theme.colors.border};
  border-radius: 14px;
  padding: 0.9rem;
`;

const DashboardGrid = styled.div`
  display: grid;
  grid-template-columns: repeat(3, minmax(260px, 1fr));
  gap: 1.05rem;
  @media (max-width: 1120px) {
    grid-template-columns: repeat(2, minmax(260px, 1fr));
  }
  @media (max-width: 680px) {
    grid-template-columns: 1fr;
  }
`;

const KpiGrid = styled.div`
  display: grid;
  grid-template-columns: repeat(3, minmax(220px, 1fr));
  gap: 1.05rem;
  margin-bottom: 1.05rem;
  @media (max-width: 1120px) {
    grid-template-columns: repeat(2, minmax(220px, 1fr));
  }
  @media (max-width: 680px) {
    grid-template-columns: 1fr;
  }
`;

const BreakdownGrid = styled(DashboardGrid)`
  margin-top: 0;
`;

/** Смуга вибору періоду (фільтр зліва) */
const HeroCard = styled(Card)`
  margin-bottom: 0.75rem;
  padding: 0.75rem 1rem;
`;

const HeroToolbar = styled.div`
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: flex-start;
  gap: 0.85rem 1rem;
`;

const HeroToolbarHint = styled.span`
  font-size: 0.88rem;
  color: ${({ theme }) => theme.colors.subtleText};
  font-weight: 500;
  margin-left: auto;
  text-align: right;
  max-width: min(100%, 280px);
  line-height: 1.35;
`;

const ManagerSelect = styled.select`
  border-radius: 999px;
  padding: 0.45rem 0.9rem;
  font-size: 0.85rem;
  border: 1px solid rgba(255, 255, 255, 0.15);
  background: rgba(255, 255, 255, 0.06);
  color: #fff;
  outline: none;
  cursor: pointer;

  option {
    color: #0f172a;
  }
`;

const FilterGroup = styled.div`
  display: flex;
  align-items: center;
  gap: 0.6rem;
  background: rgba(255, 255, 255, 0.04);
  padding: 0.35rem 0.5rem;
  border-radius: 999px;
  border: 1px solid rgba(255, 255, 255, 0.08);
`;

const FilterButton = styled.button`
  border-radius: 999px;
  padding: 0.4rem 0.85rem;
  font-size: 0.85rem;
  cursor: pointer;
  border: 1px solid transparent;
  background: ${({ $active }) => ($active ? 'rgba(255, 255, 255, 0.12)' : 'transparent')};
  color: #fff;
  font-weight: ${({ $active }) => ($active ? '600' : '400')};
  transition: all 0.18s ease;
  white-space: nowrap;

  &:hover {
    background: rgba(255, 255, 255, 0.08);
    border-color: rgba(255, 255, 255, 0.2);
  }
`;

const PendingCard = styled(Card)`
  margin-top: 1.2rem;
  cursor: default;
`;

const PendingHint = styled.div`
  font-size: 0.85rem;
  color: rgba(255, 255, 255, 0.5);
  max-width: 340px;
  line-height: 1.45;
  text-align: right;
  @media (max-width: 720px) {
    text-align: left;
    max-width: none;
  }
`;

const PendingGroupList = styled.div`
  display: flex;
  gap: 0.85rem;
  flex-wrap: wrap;
`;

const PendingGroupButton = styled.button`
  border-radius: 12px;
  padding: 0.6rem 1rem;
  font-size: 0.9rem;
  cursor: pointer;
  border: 1px solid rgba(255, 255, 255, 0.15);
  background: rgba(255, 255, 255, 0.08);
  color: #fff;
  transition: all 0.18s ease;
  display: flex;
  align-items: center;
  gap: 0.5rem;

  &:hover {
    transform: translateY(-1px);
    border-color: #fff;
    background: rgba(255, 255, 255, 0.15);
  }

  span.count {
    background: rgba(255, 255, 255, 0.12);
    padding: 0.1rem 0.45rem;
    border-radius: 6px;
    font-weight: 700;
    font-size: 0.8rem;
  }
`;

const DrilldownList = styled.div`
  margin-top: 1rem;
  display: grid;
  gap: 0.8rem;
  overflow-y: auto;
  max-height: 480px;
  padding-right: 0.5rem;

  &::-webkit-scrollbar {
    width: 6px;
  }
  &::-webkit-scrollbar-thumb {
    background: rgba(255, 255, 255, 0.12);
    border-radius: 10px;
  }
`;

const DrilldownRow = styled.button`
  width: 100%;
  text-align: left;
  padding: 1rem 1.1rem;
  border-radius: 14px;
  border: 1px solid rgba(255, 255, 255, 0.08);
  background: rgba(255, 255, 255, 0.02);
  display: flex;
  flex-direction: column;
  gap: 0.4rem;
  cursor: pointer;
  transition: all 0.18s ease;

  &:hover {
    background: rgba(255, 255, 255, 0.06);
    border-color: rgba(104, 123, 255, 0.4);
    transform: translateX(4px);
  }
`;

const LegendRow = styled.div`
  display: flex;
  flex-wrap: wrap;
  gap: 0.75rem 1.1rem;
  margin-top: 0.8rem;
  align-items: center;
`;

const LegendItem = styled.div`
  display: inline-flex;
  align-items: center;
  gap: 0.55rem;
  font-size: 0.92rem;
  color: ${({ theme }) => theme.colors.subtleText};
`;

const LegendDot = styled.span`
  width: 10px;
  height: 10px;
  border-radius: 3px;
  background: ${({ $color }) => $color};
  box-shadow: 0 0 0 2px rgba(0, 0, 0, 0.12);
`;

const DrilldownTitle = styled.strong`
  font-size: 1.05rem;
  color: #fff;
`;

const DrilldownMeta = styled.div`
  color: ${({ theme }) => theme.colors.subtleText};
  font-size: 0.92rem;
  line-height: 1.45;
`;

const StatusBadgeMinimal = styled.span`
  font-size: 0.72rem;
  padding: 0.2rem 0.5rem;
  border-radius: 6px;
  background: ${({ $color }) => ($color || 'rgba(255,255,255,0.12)')};
  color: #fff;
  font-weight: 700;
  text-transform: uppercase;
  margin-left: auto;
`;
const Header = styled.div`
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 0.7rem;
`;
const Expand = styled.button`
  border: none;
  border-radius: 10px;
  padding: 0.35rem 0.55rem;
  background: rgba(255,255,255,0.08);
  color: ${({ theme }) => theme.colors.text};
  cursor: pointer;
`;
const Overlay = styled.div`
  position: fixed;
  inset: 0;
  background: rgba(0,0,0,0.45);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 90;
`;
const Modal = styled.div`
  width: min(92vw, 980px);
  height: min(86vh, 680px);
  background: ${({ theme }) => theme.colors.cardBackground};
  border-radius: 14px;
  padding: 1rem;
`;

const StatCard = styled(Card)`
  padding: 1.05rem 1.1rem;
  display: flex;
  flex-direction: column;
  gap: 0.35rem;
  strong {
    font-size: 2.2rem;
    line-height: 1.05;
    letter-spacing: -0.02em;
  }
  span {
    font-size: 0.92rem;
    color: ${({ theme }) => theme.colors.textSecondary || theme.colors.subtleText};
  }
`;

const chartColors = ['#5f7dff', '#51d7aa', '#ffb969', '#ff7d9c'];

const statusLabelUa = (status) => {
  const key = String(status || '').toLowerCase();
  const map = {
    new: 'новий',
    waiting: 'очікує',
    call_lead: 'потрібен дзвінок',
    confirmed: 'підтверджено',
    rejected: 'відхилено',
    snoozed: 'відкладено',
    postponed: 'перенесено',
    in_work: 'в роботі',
    assigned: 'призначено',
    email_sent: 'лист надіслано',
    closed: 'закрито',
    lost: 'втрачено',
  };
  return map[key] || key || '—';
};

const parseLeadReceived = (value) => {
  if (!value) return null;
  const d = new Date(value);
  return Number.isNaN(d.getTime()) ? null : d;
};

const ActionListWrap = styled.div`
  display: flex;
  flex-direction: column;
  gap: 0.65rem;
  margin-top: 0.35rem;
  max-height: 300px;
  overflow-y: auto;
  padding-right: 0.35rem;

  &::-webkit-scrollbar {
    width: 6px;
  }
  &::-webkit-scrollbar-thumb {
    background: rgba(255, 255, 255, 0.12);
    border-radius: 10px;
  }
`;

const ActionRowBox = styled.div`
  border-radius: 12px;
  border: 1px solid rgba(255, 255, 255, 0.1);
  background: rgba(255, 255, 255, 0.03);
  padding: 0.7rem 0.85rem;
  display: flex;
  flex-direction: column;
  gap: 0.45rem;
`;

const ActionRowTop = styled.div`
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 0.5rem;
`;

const ActionReason = styled.span`
  font-size: 0.72rem;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.04em;
  color: rgba(255, 255, 255, 0.55);
  white-space: nowrap;
`;

const ActionOpenBtn = styled.button`
  align-self: flex-start;
  border-radius: 999px;
  padding: 0.35rem 0.75rem;
  font-size: 0.8rem;
  cursor: pointer;
  border: 1px solid rgba(104, 123, 255, 0.45);
  background: rgba(104, 123, 255, 0.18);
  color: #fff;
  transition: background 0.15s ease, border-color 0.15s ease;

  &:hover {
    background: rgba(104, 123, 255, 0.32);
    border-color: rgba(104, 123, 255, 0.75);
  }
`;

const ActionSub = styled.div`
  font-size: 0.85rem;
  color: ${({ theme }) => theme.colors.subtleText};
  line-height: 1.35;
`;

const AnalyticsManager = () => {
  const navigate = useNavigate();
  const { activeModals, openModal, closeModal } = useModalManager();
  const [metrics, setMetrics] = useState({ stats: {}, line: [], month: [], pie: [] });
  const [leads, setLeads] = useState([]);
  const [pendingGroups, setPendingGroups] = useState([]);
  const [drilldownStatus, setDrilldownStatus] = useState(null);
  const [rangeKey, setRangeKey] = useState('all');
  const [selectedManager, setSelectedManager] = useState('all');
  const { leadSnapshot, updateLeadSnapshot } = useAuth();
  const didHydrateRef = useRef(false);

  const rangeDays =
    rangeKey === 'all' ? null : rangeKey === 'year' ? 365 : rangeKey === 'month' ? 30 : 7;

  useEffect(() => {
    if (!didHydrateRef.current && leadSnapshot) {
      didHydrateRef.current = true;
      setLeads(leadSnapshot?.leads || []);
      setMetrics({
        stats: leadSnapshot?.stats || {},
        line: leadSnapshot?.line || [],
        month: leadSnapshot?.month || [],
        pie: leadSnapshot?.pie || [],
      });
      setPendingGroups(leadSnapshot?.pending_groups || []);
    }
  }, [leadSnapshot]); // hydrate once when snapshot appears

  useEffect(() => {
    (async () => {
      const payload = await getGmailLeads(rangeDays);
      setLeads(payload?.leads || []);
      setMetrics({
        stats: payload?.stats || {},
        line: payload?.line || [],
        month: payload?.month || [],
        pie: payload?.pie || [],
      });
      setPendingGroups(payload?.pending_groups || []);
      updateLeadSnapshot?.(payload);
    })();
  }, [updateLeadSnapshot, rangeDays]);

  const managerOptions = useMemo(() => {
    const names = Array.from(
      new Set(
        (leads || [])
          .map((lead) => lead.assigned_username || 'Не призначено')
          .filter(Boolean)
      )
    ).sort((a, b) => a.localeCompare(b));
    return ['all', ...names];
  }, [leads]);

  const filteredLeads = useMemo(() => {
    if (selectedManager === 'all') return leads;
    return leads.filter((lead) => (lead.assigned_username || 'Не призначено') === selectedManager);
  }, [leads, selectedManager]);

  const filteredPendingGroups = useMemo(() => {
    if (selectedManager === 'all') return pendingGroups;
    return (pendingGroups || []).map((group) => {
      const leadsInGroup = (group.leads || []).filter(
        (lead) => (lead.assigned_username || 'Не призначено') === selectedManager
      );
      return {
        ...group,
        leads: leadsInGroup,
        count: leadsInGroup.length,
      };
    });
  }, [pendingGroups, selectedManager]);

  const statusDistribution = useMemo(() => {
    const map = {};
    filteredLeads.forEach((lead) => {
      const key = (lead.status || 'NEW').toUpperCase();
      map[key] = (map[key] || 0) + 1;
    });
    return Object.entries(map).map(([name, value]) => ({ name, value }));
  }, [filteredLeads]);

  const managerStatuses = useMemo(() => {
    const map = {};
    filteredLeads.forEach((lead) => {
      const manager = lead.assigned_username || 'Не призначено';
      if (!map[manager]) map[manager] = 0;
      map[manager] += 1;
    });
    return Object.entries(map).map(([name, value]) => ({ name, value }));
  }, [filteredLeads]);

  const drilldownLeads = useMemo(() => {
    if (!drilldownStatus) return [];
    const key = String(drilldownStatus || '').toUpperCase();
    return filteredLeads.filter((lead) => String((lead.status || 'NEW')).toUpperCase() === key);
  }, [drilldownStatus, filteredLeads]);

  const activityDynamics = metrics.month || [];
  const statusOverTime = metrics.line || [];

  const kpis = useMemo(() => {
    const isFinal = (status) =>
      ['CONFIRMED', 'REJECTED', 'CLOSED', 'LOST', 'EMAIL_SENT'].includes(
        String(status || '').toUpperCase()
      );
    const active = filteredLeads.filter((lead) => !isFinal(lead.status)).length;
    const completed = filteredLeads.length;
    const totalEmailsAllTime =
      selectedManager === 'all'
        ? Number(metrics.stats?.total_emails_all_time ?? completed)
        : completed;
    return [
      { label: 'Кількість Активних Проєктів', value: active, hint: 'в роботі' },
      { label: 'Завершені Проєкти', value: completed, hint: 'за цей період' },
      { label: 'Листів за весь час', value: totalEmailsAllTime, hint: 'усі в базі' },
    ];
  }, [filteredLeads, metrics.stats, selectedManager]);

  const completionPct = useMemo(() => {
    if (!kpis[1]?.value) return 0;
    return Math.round(((kpis[1].value - kpis[0].value) / kpis[1].value) * 100);
  }, [kpis]);

  /** Очікує >3 дні, потрібен дзвінок, новий без відповіді — до 10 унікальних лідів */
  const priorityActionLeads = useMemo(() => {
    const now = Date.now();
    const scored = [];

    filteredLeads.forEach((lead) => {
      const st = String(lead.status || '').toLowerCase();
      const db = String(lead.status || '').toUpperCase();
      const dt = parseLeadReceived(lead.received_at);
      const ts = dt ? dt.getTime() : 0;
      const daysSince = dt ? (now - ts) / 86400000 : 0;
      const hasReply = !!(lead.last_reply_body && String(lead.last_reply_body).trim());

      let tier = null;
      let reason = '';
      /** sortKey: для tier 1 менше = старіше (пріоритетніші прострочені) */
      let sortKey = 0;

      if (st === 'waiting' && daysSince > 3) {
        tier = 1;
        reason = 'Очікує >3 дні';
        sortKey = ts || Number.MAX_SAFE_INTEGER;
      } else if (db === 'CALL_LEAD' || st === 'call_lead') {
        tier = 2;
        reason = 'Потрібен дзвінок';
        sortKey = -ts;
      } else {
        const isNew = !st || st === 'new' || db === 'NEW';
        if (isNew && !hasReply) {
          tier = 3;
          reason = 'Новий без відповіді';
          sortKey = -ts;
        }
      }

      if (tier != null) {
        scored.push({ lead, tier, reason, sortKey });
      }
    });

    scored.sort((a, b) => {
      if (a.tier !== b.tier) return a.tier - b.tier;
      if (a.tier === 1) return a.sortKey - b.sortKey;
      return a.sortKey - b.sortKey;
    });

    const seen = new Set();
    const out = [];
    for (const item of scored) {
      const key = item.lead.gmail_id || item.lead.email || JSON.stringify(item.lead);
      if (seen.has(key)) continue;
      seen.add(key);
      out.push(item);
      if (out.length >= 10) break;
    }
    return out;
  }, [filteredLeads]);

  const openChart = (id, title) =>
    openModal({ id: `chart-${id}`, type: 'chart_modal', props: { title, chartId: id } });

  const openPendingModal = (group) =>
    openModal({
      id: `pending-${group?.key}`,
      type: 'pending_modal',
      props: { title: `Очікують: ${group?.label}`, group },
    });

  const expanded = activeModals.filter((modal) => ['chart_modal', 'pending_modal'].includes(modal.type));

  const renderExpanded = (item) => {
    const id = item.props?.chartId;
    const title = item.props?.title;

    if (item.type === 'pending_modal') {
      const group = item.props?.group;
      return (
        <Overlay key={item.id} onClick={() => closeModal(item.id)}>
          <Modal onClick={(e) => e.stopPropagation()}>
            <Header>
              <h3>{title}</h3>
              <Expand onClick={() => closeModal(item.id)}>Закрити</Expand>
            </Header>

            <DrilldownList>
              {(group?.leads || []).map((lead) => {
                const status = (lead.status || 'new').toLowerCase();
                const statusColor = status === 'call_lead' ? '#f59e0b' : 
                                   status === 'confirmed' ? '#10b981' :
                                   status === 'rejected' ? '#ef4444' : '#3b82f6';
                
                return (
                  <DrilldownRow 
                    key={lead.gmail_id || lead.email}
                    onClick={() => {
                      closeModal(item.id);
                      if (lead.email) {
                        navigate('/work-zone', { state: { openLeadEmail: lead.email } });
                      }
                    }}
                  >
                    <div style={{ display: 'flex', width: '100%', alignItems: 'flex-start' }}>
                      <DrilldownTitle>{lead.full_name || lead.email || 'Лід'}</DrilldownTitle>
                      <StatusBadgeMinimal $color={statusColor}>{statusLabelUa(status)}</StatusBadgeMinimal>
                    </div>
                    <DrilldownMeta>
                      {lead.company || lead.company_name || '—'} · {lead.subject || 'Без теми'}
                      <br />
                      Отримано: {lead.received_at || '—'}
                    </DrilldownMeta>
                    {!!lead.rejection_reason && (
                      <DrilldownMeta style={{ marginTop: '4px', padding: '4px 8px', background: 'rgba(239, 68, 68, 0.1)', borderRadius: '6px', color: '#fca5a5' }}>
                        Причина: {lead.rejection_reason}
                      </DrilldownMeta>
                    )}
                  </DrilldownRow>
                );
              })}
              {!group?.leads?.length && <DrilldownMeta>Немає даних для цього групування.</DrilldownMeta>}
            </DrilldownList>
          </Modal>
        </Overlay>
      );
    }

    return (
      <Overlay key={item.id} onClick={() => closeModal(item.id)}>
        <Modal onClick={(e) => e.stopPropagation()}>
          <Header>
            <h3>{title}</h3>
            <Expand onClick={() => closeModal(item.id)}>Закрити</Expand>
          </Header>
          <ResponsiveContainer width="100%" height="90%">
            {id === 'percentage' ? (
              <PieChart>
                <Pie
                  data={[
                    { name: 'виконано', value: completionPct },
                    { name: 'залишилось', value: Math.max(0, 100 - completionPct) },
                  ]}
                  dataKey="value"
                  innerRadius={120}
                  outerRadius={170}
                  startAngle={90}
                  endAngle={450}
                  label={({ value }) => `${value}%`}
                  labelLine={false}
                >
                  <Cell fill={chartColors[1]} />
                  <Cell fill="rgba(255,255,255,0.12)" />
                </Pie>
                <text x="50%" y="50%" textAnchor="middle" dominantBaseline="middle" fontSize="68" fill="currentColor">
                  {completionPct}%
                </text>
                <Tooltip />
              </PieChart>
            ) : id === 'distribution' ? (
              <PieChart>
                <Pie
                  data={statusDistribution}
                  dataKey="value"
                  nameKey="name"
                  outerRadius={180}
                  label={({ value }) => String(value)}
                  labelLine={false}
                >
                  {statusDistribution.map((entry, index) => <Cell key={entry.name} fill={chartColors[index % chartColors.length]} />)}
                </Pie>
                <Tooltip />
              </PieChart>
            ) : id === 'dynamics' ? (
              <LineChart data={activityDynamics}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="name" />
                <YAxis />
                <Tooltip />
                <Line dataKey="pv" stroke={chartColors[0]} />
                <Line dataKey="uv" stroke={chartColors[1]} />
              </LineChart>
            ) : id === 'status-time' ? (
              <LineChart data={statusOverTime}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="name" />
                <YAxis />
                <Tooltip />
                <Line dataKey="pv" stroke={chartColors[2]} />
                <Line dataKey="uv" stroke={chartColors[3]} />
              </LineChart>
            ) : (
              <BarChart data={managerStatuses}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="name" />
                <YAxis />
                <Tooltip />
                <Bar dataKey="value" label={{ position: 'top', fill: '#fff' }}>
                  {managerStatuses.map((entry, index) => (
                    <Cell key={entry.name} fill={chartColors[index % chartColors.length]} />
                  ))}
                </Bar>
              </BarChart>
            )}
          </ResponsiveContainer>
        </Modal>
      </Overlay>
    );
  };

  return (
    <>
      <HeroCard>
        <HeroToolbar>
          <FilterGroup>
            <FilterButton type="button" $active={rangeKey === 'all'} onClick={() => setRangeKey('all')}>
              Весь час
            </FilterButton>
            <FilterButton type="button" $active={rangeKey === 'year'} onClick={() => setRangeKey('year')}>
              Рік
            </FilterButton>
            <FilterButton type="button" $active={rangeKey === 'month'} onClick={() => setRangeKey('month')}>
              Місяць
            </FilterButton>
            <FilterButton type="button" $active={rangeKey === 'week'} onClick={() => setRangeKey('week')}>
              Тиждень
            </FilterButton>
          </FilterGroup>
          <ManagerSelect
            value={selectedManager}
            onChange={(e) => {
              setSelectedManager(e.target.value);
              setDrilldownStatus(null);
            }}
          >
            {managerOptions.map((manager) => (
              <option key={manager} value={manager}>
                {manager === 'all' ? 'Усі менеджери' : manager}
              </option>
            ))}
          </ManagerSelect>
          <HeroToolbarHint>Період для метрик нижче</HeroToolbarHint>
        </HeroToolbar>
      </HeroCard>

      <KpiGrid>
        {kpis.map((item) => (
          <StatCard key={item.label}>
            <span>{item.label}</span>
            <strong>{item.value}</strong>
            <span>{item.hint}</span>
          </StatCard>
        ))}
      </KpiGrid>

      <BreakdownGrid>
        <Card>
          <Header>
            <h4>Відсоток виконання</h4>
            <Expand onClick={() => openChart('percentage', 'Відсоток виконання')}>Розгорнути</Expand>
          </Header>
          <ResponsiveContainer width="100%" height={220}>
            <PieChart>
              <Pie
                data={[
                  {
                    name: 'Виконано',
                    value: completionPct,
                  },
                  {
                    name: 'Залишилось',
                    value: Math.max(0, 100 - completionPct),
                  },
                ]}
                dataKey="value"
                innerRadius={70}
                outerRadius={90}
                startAngle={90}
                endAngle={450}
                label={({ value }) => `${value}%`}
                labelLine={false}
              >
                <Cell fill={chartColors[1]} />
                <Cell fill="rgba(255,255,255,0.12)" />
              </Pie>
              <text x="50%" y="50%" textAnchor="middle" dominantBaseline="middle" fontSize="44" fill="currentColor">
                {completionPct}%
              </text>
              <Tooltip />
            </PieChart>
          </ResponsiveContainer>
          <LegendRow>
            <LegendItem>
              <LegendDot $color={chartColors[1]} />
              Виконано
            </LegendItem>
            <LegendItem>
              <LegendDot $color="rgba(255,255,255,0.12)" />
              Залишилось
            </LegendItem>
          </LegendRow>
        </Card>

        <Card>
          <Header>
            <h4>Розподіл лідів</h4>
            <Expand onClick={() => openChart('distribution', 'Розподіл лідів')}>Розгорнути</Expand>
          </Header>
          <ResponsiveContainer width="100%" height={220}>
            <PieChart>
              <Pie
                data={statusDistribution}
                dataKey="value"
                nameKey="name"
                outerRadius={80}
                label={({ value }) => String(value)}
                labelLine={false}
              >
                {statusDistribution.map((entry, index) => (
                  <Cell
                    key={entry.name}
                    fill={chartColors[index % chartColors.length]}
                    onClick={() =>
                      setDrilldownStatus((prev) => (prev === entry.name ? null : entry.name))
                    }
                    style={{ cursor: 'pointer' }}
                  />
                ))}
              </Pie>
              <Tooltip />
            </PieChart>
          </ResponsiveContainer>
          <LegendRow>
            {statusDistribution.map((entry, index) => (
              <LegendItem key={`${entry.name}-${index}`}>
                <LegendDot
                  $color={chartColors[index % chartColors.length]}
                />
                {entry.name}
              </LegendItem>
            ))}
          </LegendRow>
        </Card>

        <Card>
          <Header>
            <h4>Ліди за менеджерами</h4>
            <Expand onClick={() => openChart('manager', 'Ліди за менеджерами')}>Розгорнути</Expand>
          </Header>
          <ResponsiveContainer width="100%" height={220}>
            <BarChart data={managerStatuses}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis dataKey="name" />
              <YAxis />
              <Tooltip />
              <Bar dataKey="value" label={{ position: 'top', fill: '#fff' }}>
                {managerStatuses.map((entry, index) => (
                  <Cell key={entry.name} fill={chartColors[index % chartColors.length]} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
          <LegendRow>
            {managerStatuses.map((entry, index) => (
              <LegendItem key={`${entry.name}-${index}`}>
                <LegendDot $color={chartColors[index % chartColors.length]} />
                {entry.name}
              </LegendItem>
            ))}
          </LegendRow>
        </Card>

        <Card>
          <Header>
            <h4>Динаміка активності</h4>
            <Expand onClick={() => openChart('dynamics', 'Динаміка активності')}>Розгорнути</Expand>
          </Header>
          <ResponsiveContainer width="100%" height={220}>
            <LineChart data={activityDynamics}>
              <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)" />
              <XAxis dataKey="name" stroke="#9ca3af" fontSize={12} />
              <YAxis stroke="#9ca3af" fontSize={12} />
              <Tooltip
                contentStyle={{ background: '#1e293b', border: '1px solid rgba(255,255,255,0.1)', borderRadius: '10px' }}
              />
              <Line type="monotone" dataKey="pv" stroke={chartColors[0]} strokeWidth={2} dot={{ r: 4 }} activeDot={{ r: 6 }} />
              <Line type="monotone" dataKey="uv" stroke={chartColors[1]} strokeWidth={2} dot={{ r: 4 }} activeDot={{ r: 6 }} />
            </LineChart>
          </ResponsiveContainer>
          <LegendRow>
            <LegendItem>
              <LegendDot $color={chartColors[0]} />
              Всього лідів
            </LegendItem>
            <LegendItem>
              <LegendDot $color={chartColors[1]} />
              Кваліфіковані
            </LegendItem>
          </LegendRow>
        </Card>

        <Card>
          <Header>
            <h4>Статуси за період</h4>
            <Expand onClick={() => openChart('status-time', 'Статуси за період')}>Розгорнути</Expand>
          </Header>
          <ResponsiveContainer width="100%" height={220}>
            <LineChart data={statusOverTime}>
              <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)" />
              <XAxis dataKey="name" stroke="#9ca3af" fontSize={12} />
              <YAxis stroke="#9ca3af" fontSize={12} />
              <Tooltip
                contentStyle={{ background: '#1e293b', border: '1px solid rgba(255,255,255,0.1)', borderRadius: '10px' }}
              />
              <Line type="monotone" dataKey="pv" stroke={chartColors[2]} strokeWidth={2} dot={{ r: 4 }} activeDot={{ r: 6 }} />
              <Line type="monotone" dataKey="uv" stroke={chartColors[3]} strokeWidth={2} dot={{ r: 4 }} activeDot={{ r: 6 }} />
            </LineChart>
          </ResponsiveContainer>
          <LegendRow>
            <LegendItem>
              <LegendDot $color={chartColors[2]} />
              Всього (міс)
            </LegendItem>
            <LegendItem>
              <LegendDot $color={chartColors[3]} />
              Кваліфіковані (міс)
            </LegendItem>
            </LegendRow>
        </Card>

        <Card>
          <Header>
            <h4>Топ пріоритетних лідів</h4>
          </Header>
          <ActionSub style={{ marginBottom: '0.25rem' }}>
            До 10 контактів: очікує понад 3 дні, потрібен дзвінок або новий без відповіді.
          </ActionSub>
          {priorityActionLeads.length === 0 ? (
            <ActionSub>Зараз немає лідів, що відповідають цим критеріям.</ActionSub>
          ) : (
            <ActionListWrap>
              {priorityActionLeads.map(({ lead, reason }) => {
                const name = lead.full_name || lead.email || 'Лід';
                const email = lead.email || '';
                return (
                  <ActionRowBox key={lead.gmail_id || email || name}>
                    <ActionRowTop>
                      <DrilldownTitle style={{ fontSize: '0.98rem' }}>{name}</DrilldownTitle>
                      <ActionReason>{reason}</ActionReason>
                    </ActionRowTop>
                    <ActionSub>
                      {(lead.company || lead.company_name || '—') + ' · ' + (lead.subject || 'Без теми')}
                      <br />
                      Отримано: {lead.received_at || '—'}
                    </ActionSub>
                    {email ? (
                      <ActionOpenBtn
                        type="button"
                        onClick={() => navigate('/work-zone', { state: { openLeadEmail: email } })}
                      >
                        Відкрити в Робочій зоні
                      </ActionOpenBtn>
                    ) : null}
                  </ActionRowBox>
                );
              })}
            </ActionListWrap>
          )}
        </Card>
      </BreakdownGrid>

      {drilldownStatus && (
        <Card style={{ marginTop: '1.2rem' }}>
          <Header>
            <h4>Деталі: {drilldownStatus}</h4>
            <Expand onClick={() => setDrilldownStatus(null)}>Згорнути</Expand>
          </Header>
          <DrilldownList>
            {drilldownLeads.map((lead) => {
              const status = (lead.status || 'new').toLowerCase();
              const statusColor = status === 'call_lead' ? '#f59e0b' : 
                                 status === 'confirmed' ? '#10b981' :
                                 status === 'rejected' ? '#ef4444' : '#3b82f6';
              return (
                <DrilldownRow 
                  key={lead.gmail_id || lead.email} 
                  onClick={() => {
                    if (lead.email) {
                      navigate('/work-zone', { state: { openLeadEmail: lead.email } });
                    }
                  }}
                >
                  <div style={{ display: 'flex', width: '100%', alignItems: 'flex-start' }}>
                    <DrilldownTitle>{lead.full_name || lead.email || 'Лід'}</DrilldownTitle>
                    <StatusBadgeMinimal $color={statusColor}>{statusLabelUa(status)}</StatusBadgeMinimal>
                  </div>
                  <DrilldownMeta>
                    {lead.company || lead.company_name || '—'} · {lead.subject || 'Без теми'}
                    <br />
                    Отримано: {lead.received_at || '—'}
                  </DrilldownMeta>
                  {!!lead.rejection_reason && (
                    <DrilldownMeta style={{ marginTop: '4px', padding: '4px 8px', background: 'rgba(239, 68, 68, 0.1)', borderRadius: '6px', color: '#fca5a5' }}>
                      Причина: {lead.rejection_reason}
                    </DrilldownMeta>
                  )}
                </DrilldownRow>
              );
            })}
          </DrilldownList>
        </Card>
      )}

      <PendingCard>
        <Header>
          <Title>Пропозиції в очікуванні</Title>
          <PendingHint>Пропозиції, що очікують відповіді більше 3-х днів</PendingHint>
        </Header>
        <PendingGroupList>
          {filteredPendingGroups.length > 0 ? (
            filteredPendingGroups.map((group) => (
              <PendingGroupButton key={group.key} onClick={() => openPendingModal(group)}>
                {group.label} <span className="count">{group.count}</span>
              </PendingGroupButton>
            ))
          ) : (
            <DrilldownMeta>Дані про очікування відсутні або завантажуються...</DrilldownMeta>
          )}
        </PendingGroupList>
      </PendingCard>

      {expanded.map(renderExpanded)}
    </>
  );
};

export default AnalyticsManager;

