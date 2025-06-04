import matplotlib.pyplot as plt
import skimage.io as io

# 加载图像
I = io.imread('coco_sample_image.jpg')
plt.imshow(I)
plt.axis('off')

# 加载和显示标注
annIds = coco.getAnnIds(imgIds=img['id'], iscrowd=None)
anns = coco.loadAnns(annIds)
coco.showAnns(anns)
plt.show()