create table chargeback_tickets (
  id uuid primary key default gen_random_uuid(),
  ticket_number text unique not null check (ticket_number ~ '^CB-[0-9]{4}-[0-9]{6}$'),
  user_id uuid not null,
  transaction_id uuid references transactions(id),
  reason_code text not null check (reason_code in ('unknown_transaction')),
  reason_label_es text not null,
  user_additional_info text,
  status text not null default 'open' check (
    status in (
      'open',
      'cancelled_by_user',
      'in_review',
      'resolved_favorable',
      'resolved_unfavorable'
    )
  ),
  resolved_by text check (resolved_by in ('agent', 'human', 'system')),
  agent_summary text,
  agent_recommendation text,
  conversation_log jsonb,
  created_at timestamptz default now(),
  updated_at timestamptz default now()
);

create or replace function set_chargeback_tickets_updated_at()
returns trigger
language plpgsql
as $$
begin
  new.updated_at := now();
  return new;
end;
$$;

create trigger trg_chargeback_tickets_updated_at
before update on chargeback_tickets
for each row
execute function set_chargeback_tickets_updated_at();
