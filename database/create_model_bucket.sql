-- Create a new bucket for trained models
insert into storage.buckets (id, name, public)
values ('trained-models', 'trained-models', true)
on conflict (id) do nothing;

-- Set up access policies
create policy "Public Access"
on storage.objects for select
using ( bucket_id = 'trained-models' );

create policy "Public Upload"
on storage.objects for insert
with check ( bucket_id = 'trained-models' );
