-- Enable RLS on nodes if not already enabled
alter table public.nodes enable row level security;

-- Policy to allow anyone (workers) to register themselves (insert)
create policy "Allow public insert on nodes"
on public.nodes
for insert
to anon
with check (true);

-- Policy to allow workers to update their own heartbeat (based on hardware_id match or just public for now for simplicity in this demo)
-- Ideally this would be signed, but for this demo, we'll allow public updates to 'last_seen'
create policy "Allow public update on nodes"
on public.nodes
for update
to anon
using (true);

-- Policy to allow everyone to see the list of nodes
create policy "Allow public select on nodes"
on public.nodes
for select
to anon
using (true);
