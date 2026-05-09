--
-- PostgreSQL database dump
--

\restrict 0K7tTMSifrlaCGsaTIAnTGq4MTsLLkZZabmB9iojSFfGxlfvFTdUwzbcWCJFlia

-- Dumped from database version 15.17 (Debian 15.17-1.pgdg13+1)
-- Dumped by pg_dump version 15.17 (Debian 15.17-1.pgdg13+1)

SET statement_timeout = 0;
SET lock_timeout = 0;
SET idle_in_transaction_session_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SELECT pg_catalog.set_config('search_path', '', false);
SET check_function_bodies = false;
SET xmloption = content;
SET client_min_messages = warning;
SET row_security = off;

--
-- Data for Name: default_category_templates; Type: TABLE DATA; Schema: public; Owner: devuser
--

INSERT INTO public.default_category_templates (id, template_key, name, created_at) VALUES (1, 'dflt-cat-0001-food', 'Food', '2026-04-26 23:23:16.748365');
INSERT INTO public.default_category_templates (id, template_key, name, created_at) VALUES (2, 'dflt-cat-0002-non-food', 'Non-Food', '2026-04-26 23:23:16.748365');
INSERT INTO public.default_category_templates (id, template_key, name, created_at) VALUES (4, '74fdcac8-41fd-4dec-a4bd-20a79c829f83', 'Dairy', '2026-05-09 17:14:07.865819');
INSERT INTO public.default_category_templates (id, template_key, name, created_at) VALUES (5, 'e611ea3d-d784-49b1-818f-14b53663ee88', 'Produce', '2026-05-09 17:14:17.286494');
INSERT INTO public.default_category_templates (id, template_key, name, created_at) VALUES (6, '150e3a9f-e4da-462f-acfe-2f0a1466b8b4', 'Meat', '2026-05-09 17:14:23.070536');
INSERT INTO public.default_category_templates (id, template_key, name, created_at) VALUES (7, '129e449f-d427-4371-af5d-59ad414a1ce7', 'Frozen', '2026-05-09 17:14:33.381343');
INSERT INTO public.default_category_templates (id, template_key, name, created_at) VALUES (8, 'facef198-5ce7-4c56-b44f-efbe7a8f8a54', 'Dry Food', '2026-05-09 17:15:12.419539');
INSERT INTO public.default_category_templates (id, template_key, name, created_at) VALUES (9, '821e5c5a-7cf3-41f1-b69f-349a4d5d2297', 'Bakery', '2026-05-09 17:15:18.214287');
INSERT INTO public.default_category_templates (id, template_key, name, created_at) VALUES (10, '2b824e18-674c-428a-a3d0-6e7e18eaf048', 'International', '2026-05-09 17:15:28.279002');
INSERT INTO public.default_category_templates (id, template_key, name, created_at) VALUES (11, '6a1e56ec-5e82-4cce-9bac-2c3911d30066', 'Cleaning', '2026-05-09 17:16:09.549278');
INSERT INTO public.default_category_templates (id, template_key, name, created_at) VALUES (12, '76f69f48-95c7-433d-a6b9-921b78204d73', 'Household', '2026-05-09 17:16:14.939367');
INSERT INTO public.default_category_templates (id, template_key, name, created_at) VALUES (13, '14b5db6c-6a37-4f8a-986c-c72ed3052ae4', 'Candy', '2026-05-09 17:16:41.873348');
INSERT INTO public.default_category_templates (id, template_key, name, created_at) VALUES (14, 'b04cdfb7-d827-42bb-b59e-729812dfe6fc', 'Pharmacy', '2026-05-09 17:16:54.443943');
INSERT INTO public.default_category_templates (id, template_key, name, created_at) VALUES (15, '89f90cdf-badd-4486-af91-3806d3a1bf9a', 'Personal Care', '2026-05-09 17:17:06.185385');
INSERT INTO public.default_category_templates (id, template_key, name, created_at) VALUES (16, 'fa589e30-46bf-4e58-b9ea-7db3bb945f9c', 'Beauty', '2026-05-09 17:17:12.406696');
INSERT INTO public.default_category_templates (id, template_key, name, created_at) VALUES (17, 'f61e24f3-be6e-4f48-8b54-4cd760bb81e3', 'Electronics', '2026-05-09 17:19:09.36745');
INSERT INTO public.default_category_templates (id, template_key, name, created_at) VALUES (18, 'b0f0cf2c-d0fb-41c9-86ea-331f84538b16', 'Bread', '2026-05-09 17:24:39.46815');
INSERT INTO public.default_category_templates (id, template_key, name, created_at) VALUES (19, 'da863cc9-f430-4d13-9f45-4de5b37a7c88', 'Pet Care', '2026-05-09 17:28:24.108819');
INSERT INTO public.default_category_templates (id, template_key, name, created_at) VALUES (20, '23f16271-f6fb-4ccb-9f53-194833c5319d', 'Coffee/Tea', '2026-05-09 17:35:47.632426');


--
-- Data for Name: default_store_templates; Type: TABLE DATA; Schema: public; Owner: devuser
--

INSERT INTO public.default_store_templates (id, template_key, name, sort_order, created_at) VALUES (1, '483d78e7-a22f-4056-802c-cfb18728744f', 'ShopRite', 0, '2026-05-09 16:56:14.479837');
INSERT INTO public.default_store_templates (id, template_key, name, sort_order, created_at) VALUES (2, '30cef0ee-c2c9-4d1f-a09a-28be0e18e77c', 'Aldi', 0, '2026-05-09 16:56:22.030252');
INSERT INTO public.default_store_templates (id, template_key, name, sort_order, created_at) VALUES (3, '1707389e-47e5-4770-b19e-40914c1d10ee', 'Costco', 0, '2026-05-09 16:56:48.140855');
INSERT INTO public.default_store_templates (id, template_key, name, sort_order, created_at) VALUES (4, 'd4f2a685-a2dd-42b0-a991-ccf122977ad4', 'Home Depot', 0, '2026-05-09 16:57:29.791584');
INSERT INTO public.default_store_templates (id, template_key, name, sort_order, created_at) VALUES (5, '8b1112ad-dc50-44bf-bd33-4eb11577d804', 'Lowes', 0, '2026-05-09 16:57:35.322319');
INSERT INTO public.default_store_templates (id, template_key, name, sort_order, created_at) VALUES (7, 'a153efc7-b6e4-4449-85b1-db7f8c60fb1a', 'Target', 0, '2026-05-09 17:11:15.132306');
INSERT INTO public.default_store_templates (id, template_key, name, sort_order, created_at) VALUES (8, '9bad5524-8353-4992-b174-d2768657a17a', 'CVS', 0, '2026-05-09 17:11:22.447394');
INSERT INTO public.default_store_templates (id, template_key, name, sort_order, created_at) VALUES (9, '95c5616c-4f13-4aa4-8db0-ff50a954e1e5', 'Electronics', 0, '2026-05-09 17:18:19.853002');
INSERT INTO public.default_store_templates (id, template_key, name, sort_order, created_at) VALUES (10, 'c5c230ac-3a37-479b-be41-e66062e534b6', 'Pet Store', 0, '2026-05-09 17:28:31.56745');


--
-- Data for Name: default_item_templates; Type: TABLE DATA; Schema: public; Owner: devuser
--

INSERT INTO public.default_item_templates (id, template_key, name, quantity, unit, category, sort_order, store_template_id, created_at) VALUES (31, 'dflt-0031-aaa-batteries', 'AAA Batteries', 10, 'each', 'Electronics', 310, 3, '2026-04-26 23:23:16.7486');
INSERT INTO public.default_item_templates (id, template_key, name, quantity, unit, category, sort_order, store_template_id, created_at) VALUES (30, 'dflt-0030-aa-batteries', 'AA Batteries', 10, 'each', 'Electronics', 300, 3, '2026-04-26 23:23:16.7486');
INSERT INTO public.default_item_templates (id, template_key, name, quantity, unit, category, sort_order, store_template_id, created_at) VALUES (4, 'dflt-0004-apples', 'Apples', 8, 'each', 'Produce', 40, 2, '2026-04-26 23:23:16.7486');
INSERT INTO public.default_item_templates (id, template_key, name, quantity, unit, category, sort_order, store_template_id, created_at) VALUES (16, 'dflt-0016-bananas', 'Bananas', 8, 'each', 'Produce', 160, 2, '2026-04-26 23:23:16.7486');
INSERT INTO public.default_item_templates (id, template_key, name, quantity, unit, category, sort_order, store_template_id, created_at) VALUES (5, 'dflt-0005-beef', 'Beef', 2.5, 'lb', 'Meat', 50, 3, '2026-04-26 23:23:16.7486');
INSERT INTO public.default_item_templates (id, template_key, name, quantity, unit, category, sort_order, store_template_id, created_at) VALUES (27, 'dflt-0027-bread-whole-wheat', 'Bread whole wheat', 2, 'loaf', 'Bread', 270, 3, '2026-04-26 23:23:16.7486');
INSERT INTO public.default_item_templates (id, template_key, name, quantity, unit, category, sort_order, store_template_id, created_at) VALUES (8, 'dflt-0008-breakfast-sausage', 'Breakfast Sausage', 2, 'lb', 'Meat', 80, 3, '2026-04-26 23:23:16.7486');
INSERT INTO public.default_item_templates (id, template_key, name, quantity, unit, category, sort_order, store_template_id, created_at) VALUES (18, 'dflt-0018-candy-hard-caramel', 'Candy hard caramel', 1, 'lb', 'Candy', 180, 1, '2026-04-26 23:23:16.7486');
INSERT INTO public.default_item_templates (id, template_key, name, quantity, unit, category, sort_order, store_template_id, created_at) VALUES (10, 'dflt-0010-cherry-peppers', 'Cherry Peppers', 1, 'lb', 'Produce', 100, 3, '2026-04-26 23:23:16.7486');
INSERT INTO public.default_item_templates (id, template_key, name, quantity, unit, category, sort_order, store_template_id, created_at) VALUES (11, 'dflt-0011-cherry-tomatoes', 'Cherry tomatoes', 2, 'lb', 'Produce', 110, 3, '2026-04-26 23:23:16.7486');
INSERT INTO public.default_item_templates (id, template_key, name, quantity, unit, category, sort_order, store_template_id, created_at) VALUES (7, 'dflt-0007-chicken-whole', 'Chicken whole', 1, 'ea', 'Meat', 70, 1, '2026-04-26 23:23:16.7486');
INSERT INTO public.default_item_templates (id, template_key, name, quantity, unit, category, sort_order, store_template_id, created_at) VALUES (15, 'dflt-0015-corn-starch', 'Corn Starch', 8, 'oz', 'Dry Food', 150, 1, '2026-04-26 23:23:16.7486');
INSERT INTO public.default_item_templates (id, template_key, name, quantity, unit, category, sort_order, store_template_id, created_at) VALUES (17, 'dflt-0017-crackers', 'Crackers', 2.5, 'lb', 'Dry Food', 170, 1, '2026-04-26 23:23:16.7486');
INSERT INTO public.default_item_templates (id, template_key, name, quantity, unit, category, sort_order, store_template_id, created_at) VALUES (28, 'dflt-0028-dishwasher-detergent', 'Dishwasher detergent', 2, 'qt', 'Cleaning', 280, 3, '2026-04-26 23:23:16.7486');
INSERT INTO public.default_item_templates (id, template_key, name, quantity, unit, category, sort_order, store_template_id, created_at) VALUES (2, 'dflt-0002-dog-food', 'Dog Food', 15, 'lb', 'Personal Care', 20, 10, '2026-04-26 23:23:16.7486');
INSERT INTO public.default_item_templates (id, template_key, name, quantity, unit, category, sort_order, store_template_id, created_at) VALUES (19, 'dflt-0019-eggs', 'Eggs', 1, 'dz', 'Dairy', 190, 2, '2026-04-26 23:23:16.7486');
INSERT INTO public.default_item_templates (id, template_key, name, quantity, unit, category, sort_order, store_template_id, created_at) VALUES (26, 'dflt-0026-egg-whites', 'Egg Whites', 1, 'qt', 'Dairy', 260, 2, '2026-04-26 23:23:16.7486');
INSERT INTO public.default_item_templates (id, template_key, name, quantity, unit, category, sort_order, store_template_id, created_at) VALUES (21, 'dflt-0021-flour', 'Flour', 2.5, 'lb', 'Dry Food', 210, 1, '2026-04-26 23:23:16.7486');
INSERT INTO public.default_item_templates (id, template_key, name, quantity, unit, category, sort_order, store_template_id, created_at) VALUES (12, 'dflt-0012-half-half', 'Half & Half', 2, 'qt', 'Dairy', 120, 2, '2026-04-26 23:23:16.7486');
INSERT INTO public.default_item_templates (id, template_key, name, quantity, unit, category, sort_order, store_template_id, created_at) VALUES (13, 'dflt-0013-heavy-cream', 'Heavy Cream', 2, 'qt', 'Dairy', 130, 2, '2026-04-26 23:23:16.7486');
INSERT INTO public.default_item_templates (id, template_key, name, quantity, unit, category, sort_order, store_template_id, created_at) VALUES (9, 'dflt-0009-leafy-greens', 'Leafy greens', 2, 'lb', 'Produce', 90, 2, '2026-04-26 23:23:16.7486');
INSERT INTO public.default_item_templates (id, template_key, name, quantity, unit, category, sort_order, store_template_id, created_at) VALUES (32, 'dflt-0032-lotion-sunblock', 'Lotion sunblock', 8, 'oz', 'Personal Care', 320, 1, '2026-04-26 23:23:16.7486');
INSERT INTO public.default_item_templates (id, template_key, name, quantity, unit, category, sort_order, store_template_id, created_at) VALUES (24, 'dflt-0024-nuts-chocolate-covered', 'Nuts Chocolate covered', 2, 'lb', 'Candy', 240, 3, '2026-04-26 23:23:16.7486');
INSERT INTO public.default_item_templates (id, template_key, name, quantity, unit, category, sort_order, store_template_id, created_at) VALUES (3, 'dflt-0003-oranges', 'Oranges', 8, 'each', 'Produce', 30, 2, '2026-04-26 23:23:16.7486');
INSERT INTO public.default_item_templates (id, template_key, name, quantity, unit, category, sort_order, store_template_id, created_at) VALUES (22, 'dflt-0022-peanut-butter-creamy', 'Peanut butter creamy', 8, 'oz', 'Dry Food', 220, 3, '2026-04-26 23:23:16.7486');
INSERT INTO public.default_item_templates (id, template_key, name, quantity, unit, category, sort_order, store_template_id, created_at) VALUES (14, 'dflt-0014-popcorn', 'Popcorn', 16, 'oz', 'Dry Food', 140, 1, '2026-04-26 23:23:16.7486');
INSERT INTO public.default_item_templates (id, template_key, name, quantity, unit, category, sort_order, store_template_id, created_at) VALUES (6, 'dflt-0006-pork', 'Pork', 2.5, 'lb', 'Meat', 60, 1, '2026-04-26 23:23:16.7486');
INSERT INTO public.default_item_templates (id, template_key, name, quantity, unit, category, sort_order, store_template_id, created_at) VALUES (1, 'dflt-0001-rice', 'Rice', 25, 'lb', 'Dry Food', 10, 3, '2026-04-26 23:23:16.7486');
INSERT INTO public.default_item_templates (id, template_key, name, quantity, unit, category, sort_order, store_template_id, created_at) VALUES (23, 'dflt-0023-steak-strips', 'Steak strips', 2, 'lb', 'Dry Food', 230, 3, '2026-04-26 23:23:16.7486');
INSERT INTO public.default_item_templates (id, template_key, name, quantity, unit, category, sort_order, store_template_id, created_at) VALUES (20, 'dflt-0020-tea-english-breakfast', 'Tea English Breakfast', 40, 'bags', 'Coffee/Tea', 200, 1, '2026-04-26 23:23:16.7486');
INSERT INTO public.default_item_templates (id, template_key, name, quantity, unit, category, sort_order, store_template_id, created_at) VALUES (29, 'dflt-0029-windex-refill', 'Windex Refill', 2, 'qt', 'Cleaning', 290, 1, '2026-04-26 23:23:16.7486');
INSERT INTO public.default_item_templates (id, template_key, name, quantity, unit, category, sort_order, store_template_id, created_at) VALUES (33, '651b3942-92e6-403f-9d9f-b9c62ab5aa80', 'Greek Yogurt', 1, NULL, 'Dairy', 0, 1, '2026-05-09 17:40:00.65339');
INSERT INTO public.default_item_templates (id, template_key, name, quantity, unit, category, sort_order, store_template_id, created_at) VALUES (34, '5cd585df-65d2-4daa-836f-28fc253a8783', 'Yogurt', 2, 'pt', 'Dairy', 0, 2, '2026-05-09 17:41:00.322141');


--
-- Name: default_category_templates_id_seq; Type: SEQUENCE SET; Schema: public; Owner: devuser
--

SELECT pg_catalog.setval('public.default_category_templates_id_seq', 20, true);


--
-- Name: default_item_templates_id_seq; Type: SEQUENCE SET; Schema: public; Owner: devuser
--

SELECT pg_catalog.setval('public.default_item_templates_id_seq', 34, true);


--
-- Name: default_store_templates_id_seq; Type: SEQUENCE SET; Schema: public; Owner: devuser
--

SELECT pg_catalog.setval('public.default_store_templates_id_seq', 10, true);


--
-- PostgreSQL database dump complete
--

\unrestrict 0K7tTMSifrlaCGsaTIAnTGq4MTsLLkZZabmB9iojSFfGxlfvFTdUwzbcWCJFlia

