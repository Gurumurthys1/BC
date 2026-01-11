-- Enable the storage extension
create extension if not exists "uuid-ossp";

-- Create Buckets
insert into storage.buckets (id, name, public) values ('training-scripts', 'training-scripts', true);
insert into storage.buckets (id, name, public) values ('datasets', 'datasets', true);

-- Policy for 'training-scripts'
-- Allow public SELECT
create policy "Public Access Training Scripts"
  on storage.objects for select
  using ( bucket_id = 'training-scripts' );

-- Allow public INSERT (for demo - in prod restrict to auth)
create policy "Public Insert Training Scripts"
  on storage.objects for insert
  with check ( bucket_id = 'training-scripts' );

-- Policy for 'datasets'
-- Allow public SELECT
create policy "Public Access Datasets"
  on storage.objects for select
  using ( bucket_id = 'datasets' );

-- Allow public INSERT (for demo)
create policy "Public Insert Datasets"
  on storage.objects for insert
  with check ( bucket_id = 'datasets' );
