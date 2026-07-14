# NEXORA Product Standard

## Purpose

NEXORA is a premium multilingual Django commerce platform for discovering, comparing, understanding, and purchasing real consumer technology. It serves Georgian, English, and Russian shoppers ranging from enthusiasts to people who need straightforward buying guidance.

## Release scope

A releasable catalogue contains at least 1,000 published real model records across phones, tablets, laptops, cameras, gaming, wearables, components, displays, audio, peripherals, printing, and adjacent technology categories. Every published record must have:

- a unique product identity, slug, SKU, and source item identifier;
- a model-matched local primary image that is not reused by another product;
- source URL, author/licence note, SHA-256 digest, perceptual hash, and verification state;
- localized name and useful short/full descriptions for Georgian, English, and Russian;
- category, brand, price, stock, variants, specifications, and searchable metadata;
- a working product page, cart action, comparison action, and administration record.

## Product principles

1. Verified reality before spectacle.
2. Expert clarity around performance, compatibility, delivery, warranty, price, and stock.
3. Cinematic restraint for video and scroll motion.
4. Server-authoritative commerce calculations and inventory.
5. One interaction system across storefront, account, checkout, guide, and administration.
6. No publication when media or provenance validation fails.

## Core journeys

Visitors can browse, search, filter, compare, save, add to cart, apply a valid coupon, and complete checkout. Customers can register, sign in, manage addresses, review eligible products, and view only their own orders. Staff can manage the full catalogue, publication state, media verification, inventory, reviews, promotions, and order status through Django Admin.

## Quality gates

A final build must pass migrations, Django system and deployment checks, the complete test suite, static collection, dependency consistency, catalogue/media integrity audits, and real-browser smoke tests at desktop and mobile widths. Essential pages must work in all three languages, both themes, keyboard-only navigation, reduced-motion mode, and with no external product-media dependency.

## Accessibility and inclusion

Target WCAG 2.2 AA with visible focus, 44 px targets, semantic structure, explicit labels, error summaries, live updates, reduced-motion support, meaningful image alternatives, sufficient contrast, and robust Georgian, English, and Russian layouts.

## Operational boundaries

The included checkout creates real local orders and updates stock transactionally. A production operator must connect a compliant payment provider, transactional email service, monitoring, backups, and deployment-specific privacy/terms content before taking live online payments.