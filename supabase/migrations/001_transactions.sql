create extension if not exists "pgcrypto";

create table transactions (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null,
  card_last4 text not null,
  card_brand text not null check (card_brand in ('visa', 'mastercard', 'amex')),
  total_amount numeric(14,2) not null,
  currency text not null check (currency in ('UYU', 'USD')),
  fx_rate numeric(10,4),
  transaction_at timestamptz not null,
  merchant_name text not null,
  merchant_dba text,
  mcc text not null,
  card_present boolean not null,
  entry_mode text check (entry_mode in ('chip', 'contactless', 'manual', 'online')),
  sales_tax numeric(14,2),
  customer_reference text,
  invoice_number text,
  merchant_postal_code text,
  merchant_city text,
  merchant_country text default 'UY',
  terminal_id text,
  ip_address text,
  is_tokenized boolean default false,
  cvm text check (cvm in ('pin', 'signature', 'biometric', 'none')),
  created_at timestamptz default now()
);

create index idx_transactions_user_transaction_at
  on transactions (user_id, transaction_at desc);

create index idx_transactions_user_merchant_name
  on transactions (user_id, merchant_name);

create index idx_transactions_user_total_amount
  on transactions (user_id, total_amount);
