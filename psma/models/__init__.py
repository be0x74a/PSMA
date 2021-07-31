from uuid import UUID

import cerberus

uuid_type = cerberus.TypeDefinition('uuid', (UUID,), ())
cerberus.Validator.types_mapping['uuid'] = uuid_type
