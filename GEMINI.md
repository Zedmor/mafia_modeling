# Mafia Modeling Project Documentation Index

This document provides a comprehensive index of all documentation files in the Mafia Modeling project, organized by category and purpose.

Use source .venv/bin/activate to active venv for the project

## Project Overview & Planning

### Core Planning Documents
- **`.taskmaster/docs/roadmap.md`** - Detailed development roadmap with milestones
- **`.taskmaster/docs/mafia_prd.md`** - Product Requirements Document for the Mafia game implementation

### Requirements & Specifications
- **`requirements.txt`** - Python package dependencies


## Game Documentation

### Game Rules & Mechanics
- **`docs/game_description.txt`** - Complete description of Mafia game rules and mechanics
- **`docs/rules.txt`** - Detailed game rules and player roles


## Technical Implementation

### Transformer Architecture
- **`docs/next_turn_token_implementation.md`** - Implementation details for the ephemeral `<NEXT_TURN>` token system
- **`.taskmaster/docs/token_grammar_specification.md`** - Complete specification of the token vocabulary and grammar
- **`docs/transformer_approach/dialogue_o3.txt`** - Research notes and approach for transformer-based game AI

### API Documentation
- **`src/mafia_server/api_doc.md`** - REST API documentation for the Mafia game server

## Test Reports & Logs

### Automated Test Reports
- **`test/logs/client_server_uat_20250622_233123/CLIENT_SERVER_UAT_REPORT.md`** - User Acceptance Test report for client-server functionality

## Documentation Categories Summary

### 📋 **Planning & Requirements** (4 files)
Core project planning, roadmaps, and requirements specification documents.

### 🎮 **Game Design** (4 files) 
Rules, mechanics, and game-specific documentation including belief calculations.

### 🤖 **Technical Architecture** (3 files)
Transformer implementation, token systems, and AI approach documentation.

### 🔧 **Development Process** (6 files)
Workflow rules, coding standards, and development guidelines for AI assistants.

### 📊 **Testing & Reports** (5 files)
Test reports, package metadata, and automated testing documentation.

### 🌐 **API & Integration** (1 file)
Server API documentation for external integrations.

## Quick Navigation by Use Case

### **New Developers**: Start Here
1. `docs/game_description.txt` - Understand the game
2. `plan.md` - Project overview
4. `docs/next_turn_token_implementation.md` - Recent technical implementation

### **AI Training & Research**: Focus On
1. `.taskmaster/docs/token_grammar_specification.md` - Token vocabulary
2. `docs/transformer_approach/dialogue_o3.txt` - AI approach
3. `docs/next_turn_token_implementation.md` - Turn signaling system
4. `docs/belief_calculator.txt` - Game state calculations

### **Game Integration**: Reference
1. `src/mafia_server/api_doc.md` - API endpoints
2. `docs/rules.txt` - Game rules implementation
3. `test/logs/*/CLIENT_SERVER_UAT_REPORT.md` - Integration test results

### **Project Management**: Track With
1. `.taskmaster/docs/roadmap.md` - Development milestones
2. `.taskmaster/docs/mafia_prd.md` - Requirements tracking

## Maintenance Notes

- **Auto-generated files**: Test reports in `test/logs/` are created automatically during test runs
- **Package metadata**: Files in `src/mafia_modeling.egg-info/` are generated during package installation
- **Configuration files**: `conftest.py`, and `pytest.ini` define project behavior

## Last Updated
This documentation index was created on 2025-06-23 and should be updated when new documentation files are added to the project.
