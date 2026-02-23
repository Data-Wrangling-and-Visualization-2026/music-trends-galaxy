# User - front/backend
There will be two stages of page lifetime:
- The first one - **initialization**: points data and manifest are fetched, while user sees the progress bar of initialization.
- The second one - **presentation**: the user views the star-point like cloud of points with labels. When the user zooms in so that the tracks' albums covers could be viewed, the app fetchs the icons from server and caches in the memory (there should be some limit on how much covers are cached), then they are displayed. When the point is clicked or hovered the info about the song and lyrics are fetched and showed.
## Backend

### Initialization API
#### 1. Fetch manifest file
Retrieve from the server the manifest file that contains all shared data used in presenting and fetching the points.
Examples of the data:
- Total number of the points
- Chunk count
- Chunk size
- Chunks 
- Cluster data:
	- deep cluster data
		- id
		- name
		- channel count
		- color
		- ...
	- wide cluster data
		- id
		- name
		- channel count
		- color
		- ...
- **Endpoint**:  `GET /init/manifest.json`
- **Description**: (put description here) 
- **Response:** application/json

Example request: (write yourself here)
Example response: (write yourself here)

#### 2. Fetch chunk data
Chunk is a collection of the points. It is stored in the `msgpack` format.

- **Endpoint**:  `GET /init/chunk/{chunk_name}`
- **Description**: (put description here) 
- **Response:** msgpack file

## Frontend
