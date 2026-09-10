# -*- coding: utf-8 -*-
"""Versioned API layer — Django REST Framework under ``/api/v1/``.

Layout:

* ``services.py``   — all business rules (validation + transactional
  writes); the single source of truth shared with ``compat.py``.
* ``serializers.py`` — DRF serializers (read shapes for every resource).
* ``views.py``      — ViewSets + infrastructure APIViews.
* ``urls.py``       — the router and non-ViewSet routes.
* ``fields.py``     — the Jalali date input field.
* ``compat.py``     — legacy-shape endpoints the current frontend calls,
  backed by the same services (thin adapters, no logic).
"""
