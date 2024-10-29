# Contributing guide

## Structure of a Django app's graphql folder

Currently most of our Django apps do not have their own `graphql` folder, their whole GraphQL schema is written up in a single file in the `graphql` app itself. Some of our apps have outgrown that single file format, so to wrangle the complexity we're trying to be consistent about the following terminology/folder structure (see the `soil_id` app for an example):

-   `mutations.py` files hold mutations.
-   `queries.py` files hold graphene types which do have resolvers for their fields (which implicity includes all `DjangoObjectType` implementers).
-   `resolvers.py` files hold resolver implementations.
-   `types.py` files hold graphene types which do not define any implementation details.
