import { ChangeEvent, DragEvent, useEffect, useId, useRef, useState } from 'react';

const ACCEPTED_IMAGE_TYPES = ['image/png', 'image/jpeg', 'image/webp'];

function formatFileSize(size: number) {
	if (size < 1024 * 1024) {
		return `${(size / 1024).toFixed(1)} KB`;
	}

	return `${(size / (1024 * 1024)).toFixed(1)} MB`;
}

export default function ImageDropzone() {
	const inputId = useId();
	const inputRef = useRef<HTMLInputElement>(null);
	const [isDragging, setIsDragging] = useState(false);
	const [error, setError] = useState<string | null>(null);
	const [selectedFile, setSelectedFile] = useState<File | null>(null);
	const [previewUrl, setPreviewUrl] = useState<string | null>(null);

	useEffect(() => {
		if (!selectedFile) {
			setPreviewUrl(null);
			return;
		}

		const objectUrl = URL.createObjectURL(selectedFile);
		setPreviewUrl(objectUrl);

		return () => {
			URL.revokeObjectURL(objectUrl);
		};
	}, [selectedFile]);

	const applyFile = (file: File | undefined) => {
		if (!file) {
			return;
		}

		if (!ACCEPTED_IMAGE_TYPES.includes(file.type)) {
			setError('Use a PNG, JPG, or WEBP image.');
			return;
		}

		setSelectedFile(file);
		setError(null);
	};

	const onInputChange = (event: ChangeEvent<HTMLInputElement>) => {
		applyFile(event.target.files?.[0]);
	};

	const onDragOver = (event: DragEvent<HTMLLabelElement>) => {
		event.preventDefault();
		setIsDragging(true);
	};

	const onDragLeave = (event: DragEvent<HTMLLabelElement>) => {
		if (event.currentTarget.contains(event.relatedTarget as Node | null)) {
			return;
		}

		setIsDragging(false);
	};

	const onDrop = (event: DragEvent<HTMLLabelElement>) => {
		event.preventDefault();
		setIsDragging(false);
		applyFile(event.dataTransfer.files?.[0]);
	};

	const clearFile = () => {
		setSelectedFile(null);
		setError(null);

		if (inputRef.current) {
			inputRef.current.value = '';
		}
	};

	return (
		<div className="dropzone-shell">
			<label
				htmlFor={inputId}
				className={`dropzone ${isDragging ? 'is-dragging' : ''} ${selectedFile ? 'has-file' : ''}`}
				onDragOver={onDragOver}
				onDragLeave={onDragLeave}
				onDrop={onDrop}
			>
				<input
					ref={inputRef}
					id={inputId}
					type="file"
					accept=".png,.jpg,.jpeg,.webp,image/png,image/jpeg,image/webp"
					onChange={onInputChange}
				/>

				<div className="dropzone-copy">
					<p className="dropzone-kicker">Image upload</p>
					<h2>{selectedFile ? 'Image ready for backend processing' : 'Drop an image here'}</h2>
					<p>
						{selectedFile
							? 'Replace it by dropping another file or choosing a new one.'
							: 'Drag and drop a PNG, JPG, or WEBP file, or choose one from your device.'}
					</p>
				</div>

				<div className="dropzone-actions" aria-hidden="true">
					<span className="dropzone-button">{selectedFile ? 'Replace image' : 'Choose image'}</span>
				</div>

				{previewUrl ? (
					<div className="dropzone-preview">
						<img src={previewUrl} alt={selectedFile?.name ?? 'Selected upload preview'} />
					</div>
				) : (
					<div className="dropzone-placeholder" aria-hidden="true">
						<div></div>
						<div></div>
					</div>
				)}
			</label>

			<div className="dropzone-meta" aria-live="polite">
				{selectedFile ? (
					<>
						<div>
							<span>Selected file</span>
							<strong>{selectedFile.name}</strong>
						</div>
						<div>
							<span>File size</span>
							<strong>{formatFileSize(selectedFile.size)}</strong>
						</div>
						<button type="button" onClick={clearFile}>
							Remove image
						</button>
					</>
				) : (
					<div>
						<span>Status</span>
						<strong>Waiting for upload</strong>
					</div>
				)}
			</div>

			{error ? <p className="dropzone-error">{error}</p> : null}
		</div>
	);
}
