# Product Requirements Document (PRD)

## Dream a Dozen – BD Gift Box Recommendation Tool (MVP)

## Overview

The BD Gift Box Recommendation Tool is an internal application designed to help the Business Development team quickly generate gift box recommendations based on client requirements. Instead of manually browsing product lists and calculating prices, the tool will recommend multiple valid gift box combinations within a specified budget and constraints.

## Problem Statement

Currently, the BD team manually creates gift box combinations by referring to spreadsheets, selecting products, calculating prices, and ensuring the final proposal fits the client's budget and preferences. This process is repetitive, time-consuming, and difficult to scale.

The objective of this tool is to automate this workflow by generating multiple valid gift box options while following predefined business rules.

## Target Users

- Business Development (BD) Team
- Internal use only

## MVP Features

### Product Database

Maintain a structured product catalog containing:

- Product Name
- Selling Price (DaD Selling Price)
- Rock Bottom Price
- Category
- Vendor
- In-house / Outsourced
- Tags (Healthy, Sweet, Savoury, etc.)

### User Inputs

The BD team should be able to specify:

- Budget
- Number of items
- Box size (optional)
- Product categories
- Preferred or mandatory products
- Products to exclude
- Preferred sweet / no sweet
- Occasion (optional)

The client may also specify custom rules, such as "Include one brownie" or "Avoid cookies," which should be supported.

### Recommendation Engine

The engine should:

- Filter products based on user constraints
- Generate only valid gift box combinations
- Calculate prices using the DaD Selling Price
- Maintain approximately a 10% pricing buffer below the client's budget
- Return 4–5 recommended gift box combinations

#### Example

**Option 1**

- Cookie A
- Cake B
- Savoury D

**Option 2**

- Brownie C
- Sandwich A
- Cupcake D

### Recommendation Prioritization

When multiple valid combinations exist, prioritize them based on:

- Closest to the client's budget
- Higher usage of in-house products
- Healthier product options

## Pricing Rules

- All recommendations use the DaD Selling Price
- Rock Bottom Price is not used during recommendation generation
- Rock Bottom Price will be reserved for a future negotiation/discount feature

## Out of Scope (MVP)

The following are intentionally excluded from the first version:

- Inventory management
- User authentication
- PDF or quotation generation
- CRM integration
- Customer-facing interface
- Recommendation memory/history

## Future Enhancements

- Occasion-based recommendations (Diwali, Christmas, etc.)
- Client preference memory
- Discount optimization using Rock Bottom Price
- Inventory availability
- Export/share proposals
- AI-assisted natural language input

## Success Criteria

The tool should enable the BD team to generate 4–5 valid gift box recommendations within seconds, reducing manual effort while ensuring recommendations align with client budgets and business constraints.